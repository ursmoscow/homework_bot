import sys
import os
import time
import logging
from http import HTTPStatus

import requests
from telegram import Bot
from dotenv import load_dotenv

from exceptions import (EmptyListException, InvalidApiExc,
                        InvalidResponseExc, InvalidJsonExc)

load_dotenv()
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)


def check_tokens():
    """Проверка наличия токенов в  переменном окружении."""
    required_tokens = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']
    missing_tokens = []

    for token in required_tokens:
        if not os.environ.get(token):
            missing_tokens.append(token)

    if missing_tokens:
        missing_tokens_str = ', '.join(missing_tokens)
        logging.critical('Отстутсвует переменная в виртуальном окружении: %s',
                         missing_tokens_str)
        return False

    return True


def send_message(bot, message):
    """Отправка сообщений ботом."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug(f'Бот отправил сообщение: {message}')
    except Exception as error:
        logger.error(f'Ошибка отправки сообщения: {error}')


def get_api_answer(timestamp):
    """Отправка запроса к API."""
    timestamp = int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except Exception as error:
        raise InvalidApiExc(f'Ошибка ответа API: {error}')
    status = homework_statuses.status_code
    if status != HTTPStatus.OK:
        logger.error(f'Ответ API: {status}')
        raise InvalidResponseExc(f'Status_code: {status}')
    try:
        return homework_statuses.json()
    except Exception as error:
        raise InvalidJsonExc(f'Ошибка декодирования JSON: {error}')


def check_response(response):
    """Проверка ответа API и получение списка списка заданий."""
    if not isinstance(response, dict):
        raise TypeError('not dict после .json() в ответе API')
    if 'homeworks' and 'current_date' not in response:
        raise InvalidApiExc('Некорректный ответ API')
    if not isinstance(response.get('homeworks'), list):
        raise TypeError('not list в ответе API по ключу homeworks')
    if not response.get('homeworks'):
        raise EmptyListException('Новых статусов нет')
    try:
        return response.get('homeworks')[0]
    except Exception as error:
        raise InvalidResponseExc(f'Из ответа не получен список работ: {error}')


def parse_status(homework):
    """Проверка статуса работы из ответа API."""
    if not homework:
        raise InvalidApiExc('Словарь homeworks пуст')
    if 'homework_name' not in homework:
        raise KeyError('Ключ homework_name отсутствует')
    if 'status' not in homework:
        raise KeyError('Ключ status отсутствует')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError(f'{homework_status} отсутствует в словаре verdicts')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = 0
    last_error = ''
    last_message = ''
    while True and check_tokens():
        try:
            logger.debug('Начало итерации, запрос к API')
            response = get_api_answer(current_timestamp)
            current_timestamp = response.get('current_date')
            homeworks = check_response(response)
            status = parse_status(homeworks)
            if status != last_message:
                send_message(bot, status)
                last_message = status
        except EmptyListException:
            logger.debug('Новых статусов в ответе API нет')
        except (InvalidApiExc, TypeError, KeyError, Exception) as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if error != last_error:
                send_message(bot, message)
                last_error = error
        else:
            logger.debug('Успешная итерация - нет исключений')
        finally:
            logger.debug('Итерация завершена')
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
