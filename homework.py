import sys
import os
import time
import logging

import requests
import telegram
from dotenv import load_dotenv


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


logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s',
                    handlers=[logging.StreamHandler(sys.stdout), ])
logger = logging.getLogger(__name__)


def check_tokens():
    """Проверка токенов в переменных окружения."""
    tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    return all(tokens)


def send_message(bot, message):
    """Отправка сообщений ботом."""
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    logger.info('Бот отправил сообщение')


def get_api_answer(timestamp):
    """Отправка запроса к API."""
    payload = {'from_date': timestamp}
    response = requests.get(
        ENDPOINT, headers=HEADERS, params=payload)
    if response.status_code != 200:
        logger.error(
            f'Сбой: Эндпоинт недоступен.'
            f'Код ответа API: {response.status_code}'
        )
        raise Exception('Код состояния HTTP не равен 200')
    response = response.json()
    return response


def check_response(response):
    """Проверка ответа API и получение списка списка заданий."""
    counter = {0: 0}
    old_status = {0: ''}
    logger.debug(response)
    if not response['homeworks']:
        logger.error('Нет данных')
        raise Exception('Нет данных')
    status = response['homeworks'][0].get('status')
    # проверка статуса согласно требованиям тестов
    if status not in HOMEWORK_VERDICTS:
        logger.error('Неизвестный статус')
        raise Exception('Неизвестный статус')
    if counter[0] == 0:
        old_status[0] = status
        counter[0] = 1
        return old_status[0]
    if counter[0] == 1:
        if status == old_status[0]:
            return False
        else:
            return status


def parse_status(homework):
    """Проверка статуса работы из ответа API."""
    status = homework.get('status')
    if status not in HOMEWORK_VERDICTS:
        logger.error('Неизвестный статус')
        raise Exception('Неизвестный статус')
    verdict = HOMEWORK_VERDICTS[status]
    homework_name = homework.get('homework_name')
    if not homework_name:
        logger.error('Нет названия домашней работы')
        raise Exception('Нет названия домашней работы')
    message = f'Изменился статус проверки работы "{homework_name}". {verdict}'
    logger.info(message)
    return message


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    if ((PRACTICUM_TOKEN == '')
            or (TELEGRAM_TOKEN == '') or (TELEGRAM_CHAT_ID == 0)):
        message = 'Отсутствуют обязательные переменные окружения'
        logger.critical(message)
        send_message(bot, message)
    timestamp = int(time.time())
    timestamp = timestamp - 86400
    while True:
        try:
            response = get_api_answer(ENDPOINT, timestamp)
            if check_response(response):
                homework = response['homeworks'][0]
                message = parse_status(homework)
                send_message(bot, message)
            time.sleep(RETRY_PERIOD)
            timestamp = int(time.time())
            timestamp = timestamp - 86400
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(
                f'Сбой в работе программы: {error}')
            send_message(bot, message)
            time.sleep(RETRY_PERIOD)
            timestamp = int(time.time())
            timestamp = timestamp - 86400
            continue


if __name__ == '__main__':
    main()
