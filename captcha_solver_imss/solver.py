"""
solver.py
Ensemble OCR para CAPTCHA alfanumérico del IMSS.

Estrategia (basada en pruebas con 11 imágenes reales):
  1. EasyOCR es el engine PRINCIPAL — funciona mejor con imágenes raw/CLAHE
  2. Tesseract es fallback de MUY baja confianza (alucina caracteres)
  3. NO binarizar — los CAPTCHA del IMSS tienen ruido que el threshold no separa
  4. Scoring realista: penaliza resultados que no parezcan CAPTCHA reales

Pipeline:
  - 5 variantes de preprocessing (raw, clahe, gray, denoised, gray_clahe)
  - EasyOCR evalúa cada variante
  - Tesseract solo si EasyOCR no encuentra nada (score penalizado)
  - Votación: wins el resultado con mejor score combinado
"""

import re
import time
import string
from pathlib import Path
from typing import Optional

import cv2
from .store import CaptchaStore
from .preprocess import preprocess_pipeline, load_image


# Caracteres válidos
UPPER = string.ascii_uppercase
DIGITS = string.digits
VALID_CHARS = set(UPPER + DIGITS)

# Thresholds
MIN_SCORE_PASS = 0.50      # mínimo para considerar "resuelto"
TESSERACT_PENALTY = 0.5    # penalización a Tesseract vs EasyOCR
EXPECTED_LEN = 7           # los CAPTCHA del IMSS son de 7 chars


class IMSCaptchaSolver:
    """
    Solver especializado para CAPTCHA del IMSS (CaptchaServlet).

    Pipeline:
      1. CNN solver (rápido, ~2ms) — primary
      2. EasyOCR ensemble (lento, ~7s) — fallback si CNN falla
      3. Tesseract (muy lento, penalizado) — fallback final

    Uso:
        solver = IMSCaptchaSolver()
        result = solver.solve(image_bytes)
        if result["success"]:
            print(result["value"])  # "CH7VNKC"
    """

    def __init__(self, store: Optional[CaptchaStore] = None,
                 use_cnn: bool = True,
                 use_easyocr: bool = True,
                 use_tesseract: bool = True,
                 verbose: bool = True,
                 cnn_model_paths: Optional[list] = None):
        """
        Args:
            store: CaptchaStore para persistencia
            use_cnn: usar CNN solver (default: True)
            use_easyocr: usar EasyOCR fallback (default: True)
            use_tesseract: usar Tesseract fallback (default: True)
            verbose: logging detallado
            cnn_model_paths: paths a modelos CNN (None = auto-select)
        """
        self.store = store
        self.verbose = verbose
        self._reader = None
        self._cnn_solver = None
        self._use_cnn = use_cnn
        self._use_easyocr = use_easyocr
        self._use_tesseract = use_tesseract and self._init_tesseract()

        if use_cnn:
            try:
                from .cnn_solver.solver_v2 import CNNSolverV2
                self._cnn_solver = CNNSolverV2(
                    model_paths=cnn_model_paths,
                    verbose=verbose,
                )
            except Exception as e:
                self._log(f"CNN no disponible: {e}")
                self._use_cnn = False

        self._log(f"IMSCaptchaSolver listo "
                  f"CNN=[{'OK' if self._use_cnn else '..'}] "
                  f"EasyOCR=[{'OK' if use_easyocr else '..'}] "
                  f"Tesseract=[{'OK' if self._use_tesseract else '..'}]")

    # ── API pública ───────────────────────────────────────────────

    def solve(self, image_source, request_id: Optional[str] = None,
              timeout_ms: int = 60000) -> dict:
        """
        Resuelve un CAPTCHA del IMSS.

        Pipeline:
          1. CNN solver (rápido, ~2ms)
          2. EasyOCR ensemble (fallback, ~7s)
          3. Tesseract (fallback final, penalizado)

        Returns:
            dict con: success, value, raw_value, engine, score, elapsed_ms, ...
        """
        start = time.time()

        # Registrar captura
        if self.store and isinstance(image_source, bytes):
            rid = self.store.save_capture(image_source, request_id)
            request_id = rid

        img = load_image(image_source)
        if img is None:
            return self._result(False, error="No se pudo cargar la imagen",
                                request_id=request_id)

        # ── 1. CNN solver (primario, siempre corre) ──────────
        cnn_available = self._use_cnn and self._cnn_solver and self._cnn_solver.is_loaded
        cnn_result = self._cnn_solver.solve(img) if cnn_available else None

        if cnn_result and cnn_result["success"] and cnn_result["value"]:
            elapsed = int((time.time() - start) * 1000)
            result = self._result(
                success=True,
                value=cnn_result["value"],
                engine="CNN",
                score=cnn_result["confidence"],
                elapsed_ms=elapsed,
                request_id=request_id,
            )
            self._log(f"  '{result['value']}' (CNN, conf={cnn_result['confidence']:.3f}, "
                      f"{elapsed}ms)")
            if self.store and request_id:
                self.store.update_result(
                    request_id, result["value"],
                    "CNN", cnn_result["confidence"], elapsed,
                )
            return result

        # ── 2. EasyOCR ensemble (fallback si CNN falló) ──────
        variants = preprocess_pipeline(img)
        n_variants = len(variants)

        candidates = self._try_easyocr(variants)

        # ── 3. Tesseract (fallback final) ────────────────────
        if not candidates and self._use_tesseract:
            candidates = self._try_tesseract(variants)

        # Consensus bonus
        self._apply_consensus_bonus(candidates)

        elapsed = int((time.time() - start) * 1000)

        if candidates:
            best = max(candidates, key=lambda c: c["score"])
            return self._finalize(best, elapsed, request_id, n_variants, candidates)

        # Sin OCR: devolver lo que CNN tenga
        if cnn_result and cnn_result["value"]:
            return self._result(
                True, value=cnn_result["value"],
                engine="CNN",
                score=cnn_result["confidence"],
                elapsed_ms=elapsed,
                request_id=request_id,
            )
        return self._result(False, error="Sin resultados",
                            elapsed_ms=elapsed, request_id=request_id)

    def _finalize(self, best, elapsed, request_id, n_variants, candidates):
        """Post-process OCR result: confusion fixes, quality floor, persist."""
        fixed_value, fixed_score = self._apply_common_fixes(
            best["value"], best["score"], candidates
        )
        if fixed_value != best["value"]:
            best["value"] = fixed_value
            best["score"] = fixed_score

        text_quality = self._score_multiplier(best["value"])
        if text_quality >= 1.0 and best["score"] < 0.50:
            old_score = best["score"]
            best["score"] = max(best["score"], 0.50)
            self._log(f"  Quality floor: {best['value']} "
                      f"score {old_score:.2f} -> {best['score']:.2f} "
                      f"(text_quality={text_quality:.2f})")

        success = best["score"] >= MIN_SCORE_PASS

        result = self._result(
            success=success,
            value=best["value"],
            raw_value=best.get("raw_value", best["value"]),
            engine=best["engine"],
            score=best["score"],
            elapsed_ms=elapsed,
            request_id=request_id,
            variants_tried=n_variants,
        )

        if self.store and request_id:
            self.store.update_result(
                request_id, result["value"],
                best["engine"], best["score"], elapsed,
            )

        status = "[OK]" if success else "[WARN]"
        self._log(f"  {status} '{result['value']}' "
                  f"(engine: {best['engine']}, "
                  f"score: {best['score']:.2f}, "
                  f"elapsed: {elapsed}ms)")
        return result

    def solve_from_path(self, path: str, **kwargs) -> dict:
        return self.solve(Path(path), **kwargs)

    # ── EasyOCR ──────────────────────────────────────────────────

    # Variantes en orden de efectividad (gray = campeón, raw = 2do, denoised = 3ro)
    # clahe, gray_clahe nunca ganaron en 11 tests — eliminados como principales
    # gradient queda como fallback (captcha XUUruEU solo se detecta con gradient)
    PRIORITY_VARIANTS = ["gray", "raw", "denoised"]
    FALLBACK_VARIANTS = ["gradient"]
    EARLY_EXIT_THRESHOLD = 0.85  # si score >= threshold + len correcto + sin chars sospechosos, cortamos

    def _is_safe_early_exit(self, text: str, score: float) -> bool:
        """Check si podemos early exit sin riesgo de falso positivo."""
        if score < self.EARLY_EXIT_THRESHOLD:
            return False
        if len(text) != EXPECTED_LEN:
            return False
        # Si tiene chars que el confusion fix podría cambiar, NO early exit
        # (necesitamos ver qué dicen las otras variantes)
        for c in text:
            for a, b in self.CONFUSION_PAIRS:
                if c == a:
                    return False
        return True

    def _try_easyocr(self, variants: dict) -> list:
        """EasyOCR sobre variantes prioritarias, con early exit greedy."""
        reader = self._get_easyocr()
        if reader is None:
            return []

        candidates = []

        for vkey in self.PRIORITY_VARIANTS:
            img = variants.get(vkey)
            if img is None:
                continue

            try:
                results = reader.readtext(img,
                                          paragraph=False,
                                          width_ths=0.7,
                                          height_ths=0.5)

                for det in results:
                    bbox, text, confidence = det
                    cleaned = self._normalize(text)
                    if cleaned:
                        mult = self._score_multiplier(cleaned)
                        score = float(confidence) * mult
                        candidates.append({
                            "value": cleaned,
                            "raw_value": text.strip(),
                            "engine": f"EasyOCR({vkey})",
                            "score": score,
                            "multiplier_orig": mult,
                            "variant": vkey,
                        })
                        if self.verbose:
                            self._log(f"  EasyOCR({vkey}): '{text}' "
                                      f"-> '{cleaned}' "
                                      f"(conf={confidence:.2f}, "
                                      f"score={score:.2f})")

                # Early exit greedy: si encontramos un candidato seguro, cortamos
                # Ahorra procesar variantes restantes cuando ya tenemos una buena respuesta
                for c in candidates:
                    if self._is_safe_early_exit(c["value"], c["score"]):
                        if self.verbose:
                            self._log(f"  Early exit en {vkey}: '{c['value']}' "
                                      f"(score {c['score']:.2f})")
                        return candidates  # return inmediato, skip variantes restantes

            except Exception as e:
                self._log(f"  EasyOCR({vkey}) error: {e}")

        # Fallback: si ningún candidato de las variantes principales tiene score >= 0.50,
        # probar variantes secundarias (gradient puede detectar chars que las otras no separan)
        if not candidates or max(c["score"] for c in candidates) < 0.50:
            for vkey in self.FALLBACK_VARIANTS:
                img = variants.get(vkey)
                if img is None:
                    continue
                try:
                    results = reader.readtext(img,
                                              paragraph=False,
                                              width_ths=0.7,
                                              height_ths=0.5)
                    for det in results:
                        bbox, text, confidence = det
                        cleaned = self._normalize(text)
                        if cleaned:
                            mult = self._score_multiplier(cleaned)
                            score = float(confidence) * mult
                            candidates.append({
                                "value": cleaned,
                                "raw_value": text.strip(),
                                "engine": f"EasyOCR({vkey})",
                                "score": score,
                                "multiplier_orig": mult,
                                "variant": vkey,
                            })
                            if self.verbose:
                                self._log(f"  EasyOCR({vkey}): '{text}' "
                                          f"-> '{cleaned}' "
                                          f"(conf={confidence:.2f}, "
                                          f"score={score:.2f})")
                except Exception as e:
                    self._log(f"  EasyOCR({vkey}) error: {e}")

        return candidates

    # ── Tesseract (fallback) ─────────────────────────────────────

    def _try_tesseract(self, variants: dict) -> list:
        """Tesseract solo como fallback, score muy penalizado."""
        import pytesseract

        candidates = []
        configs = [
            ("--psm 7", 0.5),
            ("--psm 8", 0.4),
            ("--psm 13", 0.3),
        ]

        for variant_key, variant_img in variants.items():
            if variant_img.ndim == 3:
                gray = cv2.cvtColor(variant_img, cv2.COLOR_BGR2GRAY)
            else:
                gray = variant_img

            for config_str, base_weight in configs:
                full_cfg = (
                    f"{config_str} "
                    f"-c tessedit_char_whitelist="
                    f"ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
                )
                try:
                    text = pytesseract.image_to_string(gray, config=full_cfg).strip()
                    cleaned = self._normalize(text)
                    if cleaned:
                        score = (base_weight
                                 * TESSERACT_PENALTY
                                 * self._score_multiplier(cleaned))
                        candidates.append({
                            "value": cleaned,
                            "raw_value": text,
                            "engine": f"Tesseract(psm{variant_key})",
                            "score": score,
                            "variant": variant_key,
                        })
                except Exception:
                    continue

        return candidates

    # ── Scoring ──────────────────────────────────────────────────

    def _score_multiplier(self, text: str) -> float:
        """
        Calcula qué tan "real" se ve este texto como CAPTCHA del IMSS.

        El CAPTCHA del IMSS es MIXED CASE (mayúsculas + minúsculas + dígitos).
        NO penalizar mixed case — es esperado.

        Factores:
          - Longitud ideal 6-8 (típicamente 7)
          - Ratio de caracteres válidos (A-Z, a-z, 0-9)
          - Penalización por repeticiones poco probables
          - Penalización por dígitos consecutivos largos
        """
        n = len(text)
        if n < 5 or n > 9:
            return 0.1

        # Ratio de caracteres válidos (case-sensitive: mayús y minús son válidas)
        valid = sum(1 for c in text if c.isalnum())
        ratio = valid / n if n > 0 else 0
        if ratio < 0.8:
            return 0.1

        # Bonificación por longitud cercana a 7
        len_bonus = max(0.1, 1.0 - abs(n - EXPECTED_LEN) * 0.15)

        # Penalizar secuencias de un solo carácter repetido (ej: "AAAAAAA")
        unique = len(set(text))
        uniqueness = min(1.0, unique / 3)

        # No penalizar mixed case — es normal en este CAPTCHA
        # Penalizar si tiene demasiados dígitos consecutivos
        digit_blocks = re.findall(r"\d{4,}", text)
        digit_penalty = 0.7 if digit_blocks else 1.0

        # BONIFICACIÓN por mixed case (señal de que el OCR preservó el caso real)
        has_mixed = any(c.isupper() for c in text) and any(c.islower() for c in text)
        mixed_bonus = 1.15 if has_mixed else 1.0

        final = ratio * len_bonus * uniqueness * digit_penalty * mixed_bonus
        return round(final, 3)

    def _normalize(self, text: str) -> Optional[str]:
        """
        Limpia texto OCR: preserva mixed case, solo A-Za-z0-9.
        """
        cleaned = re.sub(r"[^A-Za-z0-9]", "", text).strip()
        return cleaned if cleaned else None

    # ── Consensus bonus ─────────────────────────────────────────────

    CONSENSUS_BONUS = 0.08   # bonus por cada variante ADICIONAL que coincide
    CONSENSUS_MIN_WORDS = 2  # mínimo de variantes para activar el bonus

    def _apply_consensus_bonus(self, candidates: list):
        """
        Aplica consensus bonus: si el mismo texto aparece en múltiples
        variantes de preprocessing, sube el score (es más probable que
        sea correcto si varias variantes lo detectaron).

        También detecta textos "casi iguales" (difieren en 1 char) y
        les da un bonus menor.
        """
        if len(candidates) < self.CONSENSUS_MIN_WORDS:
            return

        # Contar ocurrencias de cada valor
        from collections import Counter
        values = [c["value"] for c in candidates if c.get("value")]
        if not values:
            return
        counts = Counter(values)

        # Bonus para cada candidato según cuántas variantes coinciden
        for c in candidates:
            v = c["value"]
            if counts[v] >= self.CONSENSUS_MIN_WORDS:
                bonus = (counts[v] - 1) * self.CONSENSUS_BONUS
                c["score"] += bonus
                if self.verbose and bonus > 0:
                    self._log(f"  Consensus bonus '{v}': +{bonus:.2f} "
                              f"(seen {counts[v]}x)")

        # Bonus parcial para textos que difieren en 1 char
        # (si "4B2mUn4" aparece 2x y "4B2mUn" aparece 1x, dan boost parcial)
        for c in candidates:
            v = c["value"]
            if counts[v] >= self.CONSENSUS_MIN_WORDS:
                continue  # ya recibió bonus completo
            for other_v, other_count in counts.items():
                if other_v == v or other_count < self.CONSENSUS_MIN_WORDS:
                    continue
                if len(other_v) == len(v):
                    diffs = sum(1 for a, b in zip(v, other_v) if a != b)
                    if diffs == 1:
                        partial = 0.04 * other_count
                        c["score"] += partial
                        if self.verbose:
                            self._log(f"  Partial consensus '{v}'~'{other_v}': "
                                      f"+{partial:.2f}")
                        break

    # ── Post-processing: confusion fixes ──────────────────────────

    # Pares (hallucinated_by_OCR, real_character) que EasyOCR confunde.
    # Primer elemento = lo que EasyOCR devuelve INCORRECTAMENTE,
    # segundo elemento = el carácter real del CAPTCHA.
    CONFUSION_PAIRS = [
        ('4', 'u'),   # EasyOCR ve 4 cuando es u
        ('h', 'n'),   # EasyOCR ve h cuando es n
        ('m', 'r'),   # EasyOCR ve m cuando es r
        ('8', 'B'),   # EasyOCR ve 8 cuando es B
        ('0', 'O'),   # EasyOCR ve 0 cuando es O
        ('1', 'l'),   # EasyOCR ve 1 cuando es l
    ]

    def _apply_common_fixes(self, text: str, current_score: float,
                             candidates: list):
        """
        Post-OCR fixes para confusiones comunes del IMSS CAPTCHA.

        Reglas:
          1. Reemplazar caracteres confundidos por EasyOCR (CONFUSION_PAIRS).
             Para caracteres duplicados, prefiere posiciones más tardías.
          2. Para textos de 8+ chars, quitar primer/último carácter extra.
          3. Para textos de 6 chars, buscar variante de 7 chars y probar
             confusión del carácter insertado.

        Returns:
            (texto_corregido, score_corregido)
        """
        if len(text) < 5 or len(text) > 9:
            return text, current_score

        orig_mult = self._score_multiplier(text)
        conf_estimate = current_score / orig_mult if orig_mult > 0 else 0.5

        def _quality(t: str) -> float:
            """Calidad de un texto como CAPTCHA (sin confianza OCR)."""
            s = self._score_multiplier(t)
            if not t:
                return s
            if t[0].isalpha():
                s += 0.05
            if len(t) >= 2 and t[-1].isdigit() and t[-2].isdigit():
                s -= 0.08
            upper = sum(1 for c in t if c.isupper() and c.isalpha())
            lower = sum(1 for c in t if c.islower() and c.isalpha())
            if upper >= 2 and lower >= 2:
                s += 0.03
            return s

        def _score_variant(t: str) -> float:
            return conf_estimate * _quality(t)

        best = (text, _score_variant(text))

        # ── 1. Reemplazar confusiones conocidas ────────────────
        # Iterar en REVERSE para que posiciones más tardías ganen en empates
        for pos in range(len(text) - 1, -1, -1):
            for a, b in self.CONFUSION_PAIRS:
                if text[pos] == a:
                    variant = text[:pos] + b + text[pos+1:]
                    score = _score_variant(variant)
                    # Bonus si otras variantes usan este carácter (evidencia extra)
                    alt_count = sum(1 for c in candidates
                                    if len(c["value"]) > pos
                                    and len(c["value"]) == len(variant)
                                    and c["value"][pos] == b)
                    if alt_count >= 1:
                        score += 0.06 * alt_count
                    # Mínimo improvement para evitar falsos positivos
                    MIN_SCORE_IMPROV = 0.05
                    if score > best[1] + MIN_SCORE_IMPROV:
                        best = (variant, score)
                        if self.verbose:
                            self._log(f"  Fix '{a}'->'{b}' pos {pos}: "
                                      f"'{text}' -> '{variant}' "
                                      f"(score {score:.2f})")

        # ── 2. Quitar primer/último carácter (textos de 8+) ───
        # Opera sobre BEST[0] (puede haber sido corregido por regla 1)
        cur = best[0]
        if len(cur) >= 8:
            for v in [cur[1:], cur[:-1], cur[1:-1]]:
                # Intentar el trim simple
                s = _score_variant(v)
                if s > best[1]:
                    best = (v, s)
                # TAMBIÉN: aplicar confusion pairs sobre el texto trimmed
                # (ej: "xbHH588" -> fix '8'->'B' -> "xbHH58B")
                # Umbral más bajo: ya estamos refinando un texto trimmed,
                # menor riesgo de falso positivo que una regla 1 completa
                MIN_SCORE_IMPROV = 0.03
                for pos2 in range(len(v) - 1, -1, -1):
                    for a, b in self.CONFUSION_PAIRS:
                        if v[pos2] == a:
                            v2 = v[:pos2] + b + v[pos2+1:]
                            s2 = _score_variant(v2)
                            if s2 > best[1] + MIN_SCORE_IMPROV:
                                best = (v2, s2)
                                if self.verbose:
                                    self._log(f"  Fix trim+'{a}'->'{b}' pos {pos2}: "
                                              f"'{v}' -> '{v2}' (score {s2:.2f})")

        # ── 3. Para textos de 6 chars, buscar variante de 7 ───
        if len(text) == 6:
            for c in candidates:
                seven = c["value"]
                if len(seven) != 7:
                    continue
                for i in range(7):
                    if seven[:i] + seven[i+1:] == text:
                        inserted = seven[i]
                        # Probar char original y su confusión real (si existe)
                        real_char = inserted
                        for a, b in self.CONFUSION_PAIRS:
                            if inserted == a:
                                real_char = b
                                break
                        # Probar primero el real_char (si es diferente)
                        for ch in ([real_char, inserted] if real_char != inserted
                                   else [inserted]):
                            variant = text[:i] + ch + text[i:]
                            # Confianza combinada: máximo entre la del texto 6-char
                            # y la del candidate 7-char
                            seven_conf = c["score"] / c.get("multiplier_orig", 1.0)
                            seven_conf = seven_conf if seven_conf > 0 else conf_estimate
                            combined_conf = max(conf_estimate, seven_conf)
                            score = combined_conf * _quality(variant)
                            if score > best[1]:
                                best = (variant, score)
                                if self.verbose:
                                    self._log(f"  Fix 6->7 insert '{inserted}'->'{ch}' "
                                              f"at {i}: '{text}' -> '{variant}' "
                                              f"(score {score:.2f})")

        return best[0], best[1]

    # ── Init ─────────────────────────────────────────────────────

    def _get_easyocr(self):
        """Lazy-load EasyOCR reader."""
        if self._reader is None:
            try:
                import os as _os
                import sys as _sys
                import io as _io
                old_out, old_err = _sys.stdout, _sys.stderr
                _sys.stdout = _io.StringIO()
                _sys.stderr = _io.StringIO()
                try:
                    import easyocr
                    self._reader = easyocr.Reader(
                        ["en"], gpu=True, verbose=False,
                    )
                    self._log("  EasyOCR listo [OK]")
                finally:
                    _sys.stdout, _sys.stderr = old_out, old_err
            except Exception as e:
                self._log(f"  EasyOCR no disponible: {e}")
                self._use_easyocr = False
                return None
        return self._reader

    def _init_tesseract(self) -> bool:
        try:
            import pytesseract
            paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            ]
            for p in paths:
                if Path(p).exists():
                    pytesseract.pytesseract.tesseract_cmd = p
                    break
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            self._log("  Tesseract no disponible")
            return False

    def _result(self, success: bool, value: str = "",
                raw_value: str = "", engine: str = "",
                score: float = 0.0, elapsed_ms: int = 0,
                request_id: str = "", variants_tried: int = 0,
                error: str = "") -> dict:
        return {
            "success": success,
            "value": value,
            "raw_value": raw_value,
            "engine": engine,
            "score": round(score, 3),
            "elapsed_ms": elapsed_ms,
            "request_id": request_id,
            "variants_tried": variants_tried,
            "error": error,
        }

    def _log(self, msg: str):
        if self.verbose:
            print(f"  [CaptchaSolver] {msg}")
