from urllib.parse import urlparse


def extract_domains(url_list, domain_list):
    """
    Извлекает домены из URL-адресов с протоколом (убирая 'www.'),
    остальные строки оставляет без изменений.
    Возвращает объединённый список обработанных строк и domain_list.
    """
    extracted = []  # отдельный список для результатов
    for url in url_list:
        if url.startswith(('http://', 'https://')):
            parsed = urlparse(url)
            host = parsed.netloc.lower()
            if host.startswith('www.'):
                host = host[4:]
            extracted.append(host)
        else:
            extracted.append(url)

    if domain_list is None:
        domain_list = []
    all_domains = list(set(extracted + domain_list))
    return all_domains
