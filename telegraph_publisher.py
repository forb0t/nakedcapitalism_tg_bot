"""
Telegraph Publisher - программа для создания статей в Telegraph
Использует официальный Telegraph API: https://telegra.ph/api
"""

import requests
import json
from typing import Optional, List, Dict, Union, Any


class TelegraphPublisher:
    """Класс для работы с Telegraph API"""
    
    BASE_URL = "https://api.telegra.ph"
    
    def __init__(self, access_token: Optional[str] = None):
        """
        Инициализация издателя Telegraph
        
        Args:
            access_token: Токен доступа Telegraph (опционально, можно создать позже)
        """
        self.access_token = access_token
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json'
        })
    
    def create_account(self, short_name: str, author_name: Optional[str] = None, 
                      author_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Создание нового аккаунта Telegraph
        
        Args:
            short_name: Имя аккаунта (1-32 символа) - обязательное
            author_name: Имя автора по умолчанию (0-128 символов)
            author_url: URL профиля автора (0-512 символов)
        
        Returns:
            Словарь с информацией об аккаунте, включая access_token
        """
        url = f"{self.BASE_URL}/createAccount"
        
        params = {'short_name': short_name}
        if author_name:
            params['author_name'] = author_name
        if author_url:
            params['author_url'] = author_url
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get('ok'):
                account = data.get('result', {})
                self.access_token = account.get('access_token')
                return account
            else:
                raise Exception(f"Ошибка создания аккаунта: {data.get('error')}")
        
        except requests.exceptions.RequestException as e:
            raise Exception(f"Ошибка запроса к API: {e}")
    
    def text_to_nodes(self, text: str) -> List[Union[str, Dict[str, Any]]]:
        """
        Преобразование текста в формат Telegraph Node
        
        Args:
            text: Текст для преобразования
        
        Returns:
            Список Node объектов для Telegraph
        """
        # Разбиваем текст на параграфы
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        nodes = []
        for paragraph in paragraphs:
            # Разбиваем на строки, если есть переносы
            lines = paragraph.split('\n')
            for line in lines:
                line = line.strip()
                if line:
                    nodes.append({
                        'tag': 'p',
                        'children': [line]
                    })
        
        return nodes if nodes else [{'tag': 'p', 'children': ['']}]
    
    def html_to_nodes(self, html_content: str) -> List[Union[str, Dict[str, Any]]]:
        """
        Базовое преобразование HTML в формат Telegraph Node
        Поддерживает основные теги: p, h3, h4, b, strong, em, i, a, br, ul, ol, li
        
        Args:
            html_content: HTML контент
        
        Returns:
            Список Node объектов для Telegraph
        """
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html_content, 'html.parser')
        nodes = []
        
        # Рекурсивная функция для преобразования элементов
        def element_to_node(elem):
            if elem.name is None:  # Текстовый узел
                text = str(elem).strip()
                return text if text else None
            
            # Поддерживаемые теги Telegraph
            supported_tags = {
                'p': 'p',
                'h1': 'h3',  # h1 преобразуется в h3
                'h2': 'h3',  # h2 преобразуется в h3
                'h3': 'h3',
                'h4': 'h4',
                'b': 'b',
                'strong': 'strong',
                'em': 'em',
                'i': 'i',
                'a': 'a',
                'br': 'br',
                'ul': 'ul',
                'ol': 'ol',
                'li': 'li',
                'blockquote': 'blockquote',
                'code': 'code',
                'pre': 'pre',
                'img': 'img',
            }
            
            tag_name = elem.name.lower()
            if tag_name not in supported_tags:
                # Если тег не поддерживается, просто извлекаем текст
                return elem.get_text(strip=True) if elem.get_text(strip=True) else None
            
            node = {'tag': supported_tags[tag_name]}
            
            # Обработка атрибутов для ссылок и изображений
            if tag_name == 'a' and elem.get('href'):
                node['attrs'] = {'href': elem.get('href')}
            elif tag_name == 'img' and elem.get('src'):
                node['attrs'] = {'src': elem.get('src')}
            
            # Обработка дочерних элементов
            children = []
            for child in elem.children:
                child_node = element_to_node(child)
                if child_node is not None:
                    if isinstance(child_node, str):
                        children.append(child_node)
                    elif isinstance(child_node, dict):
                        children.append(child_node)
            
            if children:
                node['children'] = children
            elif tag_name == 'br':
                # br не требует children
                pass
            else:
                # Если нет дочерних элементов, добавляем пустой текст
                text = elem.get_text(strip=True)
                if text:
                    node['children'] = [text]
            
            return node
        
        # Обрабатываем все элементы
        for elem in soup.children:
            if hasattr(elem, 'name') and elem.name:
                node = element_to_node(elem)
                if node and isinstance(node, dict):
                    nodes.append(node)
            elif isinstance(elem, str) and elem.strip():
                # Простой текст между элементами
                nodes.append({'tag': 'p', 'children': [elem.strip()]})
        
        return nodes if nodes else [{'tag': 'p', 'children': ['']}]
    
    def create_page(self, title: str, content: Union[str, List[Union[str, Dict[str, Any]]]], 
                    author_name: Optional[str] = None, author_url: Optional[str] = None,
                    return_content: bool = False) -> Dict[str, Any]:
        """
        Создание новой страницы в Telegraph
        
        Args:
            title: Заголовок страницы (1-256 символов) - обязательное
            content: Контент страницы:
                    - Строка (текст или HTML) - будет автоматически преобразована
                    - Список Node объектов в формате Telegraph
            author_name: Имя автора (0-128 символов)
            author_url: URL профиля автора (0-512 символов)
            return_content: Вернуть контент в ответе
        
        Returns:
            Словарь с информацией о созданной странице
        """
        if not self.access_token:
            raise Exception("Требуется access_token. Создайте аккаунт с помощью create_account()")
        
        url = f"{self.BASE_URL}/createPage"
        
        # Преобразование контента
        if isinstance(content, str):
            # Определяем, HTML это или простой текст
            if '<' in content and '>' in content:
                nodes = self.html_to_nodes(content)
            else:
                nodes = self.text_to_nodes(content)
        else:
            nodes = content
        
        # Подготовка параметров
        params = {
            'access_token': self.access_token,
            'title': title,
            'content': json.dumps(nodes, ensure_ascii=False)
        }
        
        if author_name:
            params['author_name'] = author_name
        if author_url:
            params['author_url'] = author_url
        if return_content:
            params['return_content'] = 'true'
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get('ok'):
                return data.get('result', {})
            else:
                raise Exception(f"Ошибка создания страницы: {data.get('error')}")
        
        except requests.exceptions.RequestException as e:
            raise Exception(f"Ошибка запроса к API: {e}")
    
    def get_page(self, path: str, return_content: bool = False) -> Dict[str, Any]:
        """
        Получение информации о странице Telegraph
        
        Args:
            path: Путь к странице (например, "Sample-Page-12-15")
            return_content: Вернуть контент страницы
        
        Returns:
            Словарь с информацией о странице
        """
        url = f"{self.BASE_URL}/getPage/{path}"
        
        params = {}
        if return_content:
            params['return_content'] = 'true'
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get('ok'):
                return data.get('result', {})
            else:
                raise Exception(f"Ошибка получения страницы: {data.get('error')}")
        
        except requests.exceptions.RequestException as e:
            raise Exception(f"Ошибка запроса к API: {e}")
    
    def get_account_info(self, fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Получение информации об аккаунте
        
        Args:
            fields: Список полей для возврата (по умолчанию: short_name, author_name, author_url)
        
        Returns:
            Словарь с информацией об аккаунте
        """
        if not self.access_token:
            raise Exception("Требуется access_token")
        
        url = f"{self.BASE_URL}/getAccountInfo"
        
        params = {'access_token': self.access_token}
        if fields:
            params['fields'] = json.dumps(fields)
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get('ok'):
                return data.get('result', {})
            else:
                raise Exception(f"Ошибка получения информации об аккаунте: {data.get('error')}")
        
        except requests.exceptions.RequestException as e:
            raise Exception(f"Ошибка запроса к API: {e}")


def example_usage():
    """Пример использования TelegraphPublisher"""
    
    # Пример 1: Создание аккаунта и публикация статьи из текста
    print("Пример 1: Создание аккаунта и публикация текстовой статьи")
    publisher = TelegraphPublisher()
    
    # Создаем аккаунт (если еще нет токена)
    account = publisher.create_account(
        short_name="MyBot",
        author_name="Article Publisher",
        author_url="https://t.me/mybot"
    )
    print(f"Создан аккаунт. Access token: {account.get('access_token')}")
    
    # Публикуем статью из текста
    article_text = """
    Это пример статьи для Telegraph.
    
    Статья содержит несколько параграфов с текстом.
    
    Вы можете добавлять форматирование и структурировать контент.
    """
    
    page = publisher.create_page(
        title="Пример статьи",
        content=article_text,
        author_name="Article Publisher"
    )
    print(f"Статья создана: {page.get('url')}")
    
    # Пример 2: Публикация статьи с HTML
    print("\nПример 2: Публикация HTML статьи")
    html_content = """
    <h3>Заголовок статьи</h3>
    <p>Это параграф с <b>жирным текстом</b> и <i>курсивом</i>.</p>
    <p>Также можно добавлять <a href="https://example.com">ссылки</a>.</p>
    <ul>
        <li>Элемент списка 1</li>
        <li>Элемент списка 2</li>
    </ul>
    """
    
    page2 = publisher.create_page(
        title="HTML статья",
        content=html_content,
        author_name="Article Publisher"
    )
    print(f"HTML статья создана: {page2.get('url')}")
    
    # Пример 3: Создание статьи с кастомными Node объектами
    print("\nПример 3: Создание статьи с кастомными Node объектами")
    custom_content = [
        {
            "tag": "h3",
            "children": ["Кастомная статья"]
        },
        {
            "tag": "p",
            "children": ["Это статья создана с использованием Node объектов."]
        },
        {
            "tag": "p",
            "children": [
                "Вы можете посетить ",
                {
                    "tag": "a",
                    "attrs": {"href": "https://telegra.ph"},
                    "children": ["Telegraph"]
                },
                " для получения дополнительной информации."
            ]
        }
    ]
    
    page3 = publisher.create_page(
        title="Кастомная статья",
        content=custom_content,
        author_name="Article Publisher"
    )
    print(f"Кастомная статья создана: {page3.get('url')}")


if __name__ == "__main__":
    example_usage()

