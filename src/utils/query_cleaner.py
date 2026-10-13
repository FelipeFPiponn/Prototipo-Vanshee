import re


def is_first_result_requested(raw_text: str) -> bool:
    """Detecta si el usuario solicitó explícitamente abrir o ingresar al primer enlace/resultado."""
    if not raw_text:
        return False
    pat = r"(?:(?:y\s+)?(?:abre|abrir|entra|entrar|ingresa|ingresar|navega|navegar|ir\s+a|ir\s+al)\s+(?:a\s+|en\s+|al\s+)?(?:el\s+)?(?:primer\s+|1er\s+)?(?:link|enlace|resultado|pagina|página|sitio))|(?:(?:el\s+)?(?:primer|1er)\s+(?:link|enlace|resultado|pagina|página|sitio))"
    return bool(re.search(pat, raw_text, flags=re.IGNORECASE))


def clean_search_term(raw_query: str) -> str:
    """Limpia palabras de relleno, conectores y caracteres residuales de las búsquedas.
    
    Elimina prefijos como:
    - 'canciones de', 'canción de', 'musica de', 'temas de'
    - 'videos de', 'video de', 'videos sobre', 'trailer de'
    - 'información sobre', 'noticias de'
    - comillas y signos '+' literales
    
    Elimina sufijos como:
    - 'y abre el primer link', 'y entra al primer resultado'
    - 'en el navegador', 'en internet', 'en google'
    - 'y reproduce el primer video'
    """
    if not raw_query:
        return ""

    q = str(raw_query).strip()

    # 1. Reemplazar '+' residuales por espacios normales
    q = q.replace("+", " ")

    # 2. Eliminar comillas iniciales o finales
    q = re.sub(r'^["\'«“]+|["\'»”]+$', "", q).strip()

    # 3. Lista ordenada de prefijos de relleno (de más específicos a más generales)
    prefix_patterns = [
        r"^(?:por\s+favor\s+)?(?:pon|por|reproduce|reproducir|busca|buscar|escuchar|toca|tocar)\s+(?:una\s+|un\s+|la\s+|el\s+)?(?:cancion|canción|musica|música|video|tema|pista)\s+(?:de\s+)?",
        r"^(?:por\s+favor\s+)?(?:pon|por|reproduce|reproducir|busca|buscar)\s+(?:una\s+|un\s+|la\s+|el\s+)?(?:cancion|canción|musica|música|video|tema|pista)\s+",
        r"^(?:por\s+favor\s+)?(?:pon|por|reproduce|reproducir)\s+(?:una\s+|un\s+|la\s+|el\s+)?",
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
        r"^(?:el\s+)?primer\s+video\s+(?:de|sobre)\s+",
        r"^(?:trailers?\s+(?:de|sobre)|tráilers?\s+(?:de|sobre)|gameplays?\s+(?:de|sobre))\s+",
        r"^(?:informacion\s+(?:de|sobre)|información\s+(?:de|sobre))\s+",
        r"^(?:noticias\s+(?:de|sobre)|noticia\s+(?:de|sobre))\s+",
        r"^(?:algo\s+de|un\s+poco\s+de)\s+",
    ]

    for pat in prefix_patterns:
        subbed = re.sub(pat, "", q, flags=re.IGNORECASE).strip()
        if subbed:
            q = subbed

    # 4. Lista de sufijos de relleno con multi-pass (para eliminar cadenas de sufijos como 'en el navegador y abre el primer link')
    suffix_patterns = [
        r"\s+(?:y\s+)?(?:abre|abrir|entra|entrar|ingresa|ingresar|navega|navegar|ve|ir)(?:\s+(?:a|al|en))?\s+(?:el\s+)?(?:primer\s+|1er\s+)?(?:link|enlace|resultado|pagina|página|sitio)$",
        r"\s+(?:y\s+)?(?:abre|abrir|entra|entrar|ingresa|ingresar|navega|navegar|ve|ir)\s+(?:al\s+|a\s+la\s+|al\s+primer\s+|a\s+la\s+primera\s+)(?:link|enlace|resultado|pagina|página|sitio)$",
        r"\s+(?:en\s+(?:el\s+)?)?(?:primer|1er)\s+(?:link|enlace|resultado|pagina|página|sitio)$",
        r"\s+(?:y\s+)?(?:reproduce|pon|ponlo|dale\s+play)(?:\s+(?:el\s+)?(?:primer\s+)?(?:video|cancion|canción|tema|musica|música))?$",
        r"\s+(?:y\s+)?reproduce\s+(?:el\s+)?(?:primer\s+)?(?:video|cancion|canción|tema|musica|música)$",
        r"\s+(?:y\s+)?pon\s+(?:el\s+)?(?:primer\s+)?(?:video|cancion|canción|tema|musica|música)$",
        r"\s+(?:el\s+)?(?:primer|1er)\s+(?:video|cancion|canción|tema)$",
        r"\s+en\s+(?:el\s+)?(?:navegador|buscador|internet|la\s+web)$",
        r"\s+en\s+(?:google|youtube|spotify|brave|chrome|bing|duckduckgo|edge|firefox)$",
        r"\s+en\s+(?:linea|línea)$",
        r"\s+por\s+favor$",
        r"\s+gracias$",
    ]

    changed = True
    iterations = 0
    while changed and iterations < 4:
        changed = False
        iterations += 1
        for pat in suffix_patterns:
            subbed = re.sub(pat, "", q, flags=re.IGNORECASE).strip()
            if subbed != q and subbed:
                q = subbed
                changed = True

    # Normalizar espacios múltiples
    q = re.sub(r"\s+", " ", q).strip()
    return q
