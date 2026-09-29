import re


def clean_search_term(raw_query: str) -> str:
    """Limpia palabras de relleno, conectores y caracteres residuales de las búsquedas.
    
    Elimina prefijos como:
    - 'canciones de', 'canción de', 'musica de', 'temas de'
    - 'videos de', 'video de', 'videos sobre', 'trailer de'
    - 'información sobre', 'noticias de'
    - comillas y signos '+' literales
    """
    if not raw_query:
        return ""

    q = str(raw_query).strip()

    # 1. Reemplazar '+' residuales por espacios normales
    q = q.replace("+", " ")

    # 2. Eliminar comillas iniciales o finales
    q = re.sub(r'^["\'«“]+|["\'»”]+$', "", q).strip()

    # 3. Lista ordenada de prefijos de relleno (de más específicos a más generales)
    patterns = [
        r"^(?:las\s+)?(?:mejores\s+)?canciones\s+de\s+",
        r"^(?:la\s+)?cancion\s+de\s+",
        r"^(?:la\s+)?canción\s+de\s+",
        r"^(?:las\s+)?canciones\s+",
        r"^(?:la\s+)?canción\s+",
        r"^(?:la\s+)?cancion\s+",
        r"^(?:musica|música)\s+de\s+",
        r"^(?:musica|música)\s+",
        r"^(?:temas\s+de|tema\s+de|temas|tema)\s+",
        r"^(?:album\s+de|álbum\s+de|albumes\s+de|álbumes\s+de|discografia\s+de|discografía\s+de)\s+",
        r"^(?:los\s+)?(?:mejores\s+)?videos\s+(?:de|sobre)\s+",
        r"^(?:el\s+)?video\s+(?:de|sobre)\s+",
        r"^(?:los\s+)?videos\s+",
        r"^(?:el\s+)?video\s+",
        r"^(?:trailers?\s+(?:de|sobre)|tráilers?\s+(?:de|sobre)|gameplays?\s+(?:de|sobre))\s+",
        r"^(?:informacion\s+(?:de|sobre)|información\s+(?:de|sobre))\s+",
        r"^(?:noticias\s+(?:de|sobre)|noticia\s+(?:de|sobre))\s+",
        r"^(?:algo\s+de|un\s+poco\s+de)\s+",
    ]

    for pat in patterns:
        subbed = re.sub(pat, "", q, flags=re.IGNORECASE).strip()
        # Solo adoptar el reemplazo si no vació por completo el término
        if subbed:
            q = subbed

    # Normalizar espacios múltiples
    q = re.sub(r"\s+", " ", q).strip()
    return q
