"""Emojis -> palabras (solo para lo que se embebe en los subtemas)."""
from __future__ import annotations

from app.services.percepcion import derivados, emojis, subtemas
from app.services.percepcion.emojis import emojis_a_palabras


def test_traduce_los_emojis_conocidos():
    assert emojis_a_palabras("gran trabajo 👏") == "gran trabajo aplausos"
    assert emojis_a_palabras("😡 pésimo") == "enojo pésimo"
    assert emojis_a_palabras("😭") == "tristeza"


def test_tono_distinto_para_emojis_distintos():
    assert len({emojis_a_palabras(e) for e in ("👏", "😡", "😭", "😂", "🖤", "❤")}) == 6


def test_repeticiones_seguidas_de_la_misma_palabra_se_juntan():
    assert emojis_a_palabras("👏👏👏") == "aplausos"
    assert emojis_a_palabras("👏 👏 👏") == "aplausos"
    assert emojis_a_palabras("❤💕💖") == "amor"          # distintos emojis, misma palabra
    assert emojis_a_palabras("👏🏻👏🏼👏🏽") == "aplausos"
    # Con texto entremedio no es una repetición.
    assert emojis_a_palabras("👏 bravo 👏") == "aplausos bravo aplausos"


def test_quita_tonos_de_piel_zwj_selectores_y_banderas():
    assert emojis_a_palabras("🙏🏽") == "gracias"
    assert emojis_a_palabras("❤️") == "amor"                      # con selector de variación
    assert emojis_a_palabras("❤️‍🩹") == "amor"              # la pieza unida por ZWJ se va
    assert emojis_a_palabras("🇨🇱 vamos") == "vamos"              # indicadores regionales
    assert emojis_a_palabras("♀ ok") == "ok"
    assert "‍" not in emojis_a_palabras("🤷🏻‍♀️ no sé")


def test_deja_los_emojis_desconocidos_y_el_resto_igual():
    assert emojis_a_palabras("hola 🦄") == "hola 🦄"
    assert emojis_a_palabras("sin emojis, ¿ok?") == "sin emojis, ¿ok?"
    assert emojis_a_palabras("") == "" and emojis_a_palabras(None) == ""


def test_el_diccionario_cubre_lo_pedido():
    for e in "👏❤♥💕💖💗🩷🤍💜💙💚🧡💛🖤🕊😢😭😔😞🥺😂🤣😡🤬🔥🙌🥳🎉🎊🙏🫶🫂🤗😍🥰😘💪🐾🐶😮💔👀🗣🚬":
        assert e in emojis.EMOJI_PALABRAS, e
    assert emojis.EMOJI_PALABRAS["🖤"] == "luto" and emojis.EMOJI_PALABRAS["🕊"] == "paz"


def test_limpiar_embebe_con_palabras_en_vez_de_emojis():
    assert subtemas.limpiar("Gracias por todo 👏👏 @alguien") == "Gracias por todo aplausos"
    # Un comentario de solo emojis conocidos ya no queda vacío.
    assert subtemas.limpiar("😭😭") == "tristeza"
    # Y uno de solo etiquetas sigue vacío.
    assert subtemas.limpiar("@a @b_ tote.mny_") == ""


def test_los_tokens_guardados_no_cambian_con_los_emojis():
    # `derivados` no traduce nada: los emojis se descartan igual que antes.
    assert derivados.tokenizar("excelente trabajo 👏😡") == ["excelente", "trabajo"]
    assert derivados.tokens_de("aplausos 👏") == {"aplausos"}
