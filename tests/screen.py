import threading
import time
from typing import List

import pytest
from bs4 import BeautifulSoup
from nicegui import globals, ui
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

PORT = 3392
IGNORED_CLASSES = ['row', 'column', 'q-card', 'q-field', 'q-field__label', 'q-input']


class Screen():

    def __init__(self, selenium: webdriver.Chrome) -> None:
        self.selenium = selenium
        self.server_thread = None

    def start_server(self) -> None:
        '''Start the webserver in a separate thread. This is the equivalent of `ui.run()` in a normal script.'''
        self.server_thread = threading.Thread(target=ui.run, kwargs={'port': PORT, 'show': False, 'reload': False})
        self.server_thread.start()

    def stop_server(self) -> None:
        '''Stop the webserver.'''
        self.selenium.close()
        globals.server.should_exit = True
        self.server_thread.join()

    def open(self, path: str) -> None:
        if self.server_thread is None:
            self.start_server()
        start = time.time()
        while True:
            try:
                self.selenium.get(f'http://localhost:{PORT}{path}')
                break
            except Exception:
                if time.time() - start > 3:
                    raise
                time.sleep(0.1)
                if not self.server_thread.is_alive():
                    raise RuntimeError('The NiceGUI server has stopped running')

    def should_contain(self, text: str) -> None:
        assert self.selenium.title == text or self.find(text), \
            f'could not find "{text}" on:\n{self.render_content()}'

    def should_not_contain(self, text: str) -> None:
        assert self.selenium.title != text
        with pytest.raises(AssertionError):
            element = self.find(text)
            print(element.get_attribute('outerHTML'))

    def click(self, target_text: str) -> None:
        self.find(target_text).click()

    def find(self, text: str) -> WebElement:
        try:
            return self.selenium.find_element(By.XPATH, f'//*[contains(text(),"{text}")]')
        except NoSuchElementException:
            raise AssertionError(f'Could not find "{text}" on:\n{self.render_content()}')

    def render_content(self, with_extras: bool = False) -> str:
        body = self.selenium.find_element(By.TAG_NAME, 'body').get_attribute('innerHTML')
        soup = BeautifulSoup(body, 'html.parser')
        self.simplify_input_tags(soup)
        content = ''
        for child in soup.find_all():
            is_element = False
            if child is None or child.name == 'script':
                continue
            depth = (len(list(child.parents)) - 3) * '  '
            if not child.find_all() and child.text:
                content += depth + child.getText()
                is_element = True
            classes = child.get('class', '')
            if classes:
                if classes[0] in ['row', 'column', 'q-card']:
                    content += depth + classes[0].removeprefix('q-')
                    is_element = True
                if classes[0] == 'q-field':
                    pass
                [classes.remove(c) for c in IGNORED_CLASSES if c in classes]
                for i, c in enumerate(classes):
                    classes[i] = c.removeprefix('q-field--')
                if is_element and with_extras:
                    content += f' [class: {" ".join(classes)}]'

            if is_element:
                content += '\n'

        return f'Title: {self.selenium.title}\n\n{content}'

    @staticmethod
    def simplify_input_tags(soup: BeautifulSoup) -> None:
        for element in soup.find_all(class_="q-field"):
            print(element.prettify())
            new = soup.new_tag('simple_input')
            name = element.find(class_='q-field__label').text
            placeholder = element.find(class_='q-field__native').get('placeholder')
            value = element.find(class_='q-field__native').get('value')
            new.string = (f'{name}: ' if name else '') + (value or placeholder or '')
            new['class'] = element['class']
            element.replace_with(new)

    def get_tags(self, name: str) -> List[WebElement]:
        return self.selenium.find_elements(By.TAG_NAME, name)

    def get_attributes(self, tag: str, attribute: str) -> List[str]:
        return [t.get_attribute(attribute) for t in self.get_tags(tag)]

    def wait(self, t: float) -> None:
        time.sleep(t)