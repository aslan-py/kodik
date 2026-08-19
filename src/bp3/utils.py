"""Вспомогательные функции: работа с доменами и очистка данных."""

from urllib.parse import urlparse


def extract_domains(url_list, domain_list):
    """Извлекает домены из ссылок и объединяет их с готовым списком доменов."""
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


def clear_p4_comments_actions(
    comments: list[dict], actions: list[dict], priority_dict: dict[int, str]
) -> None:
    """Убирает комментарии и рекомендации у новостей с приоритетом p4."""
    for item in comments:
        if priority_dict.get(item.get('id')) == 'p4':
            item['comments'] = None

    for item in actions:
        if priority_dict.get(item.get('id')) == 'p4':
            item['actions'] = None
