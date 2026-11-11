from __future__ import annotations

from app.evals.screen_text import token_f1, tokenize


def test_tokenize_ignora_acentos_y_palabras_cortas() -> None:
    assert tokenize("200 g de HARINA, 2 huevos") == ["200", "de", "harina", "huevos"]


def test_token_f1_premia_lo_leido_y_penaliza_lo_que_sobra() -> None:
    expected = "200 g de harina y 2 huevos"
    assert token_f1(expected, expected) == 1.0
    assert token_f1(expected, "200 g de harina") == 0.8571
    assert token_f1(expected, "") == 0.0
    assert token_f1(expected, "texto completamente distinto") == 0.0
