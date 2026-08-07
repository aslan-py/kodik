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


def clear_p4_comments_actions(
    comments: list[dict], actions: list[dict], priority_dict: dict[int, str]
) -> None:
    """
    Устанавливает comments и actions в None для записей с priority == "p4".

    Args:
        comments: список словарей с ключами 'id' и 'comments'
        actions: список словарей с ключами 'id' и 'actions'
        priority_dict: словарь {id: priority}
    """
    for item in comments:
        if priority_dict.get(item.get('id')) == 'p4':
            item['comments'] = None

    for item in actions:
        if priority_dict.get(item.get('id')) == 'p4':
            item['actions'] = None
