import argparse
import os
from aiohttp import web
import aiofiles
import asyncio
import datetime
import logging

INTERVAL_SECS = 1
chunk_size_kb = 1


def parse_args():
    parser = argparse.ArgumentParser(description="Настройки микросервиса")

    parser.add_argument('--log-level', type=str, default=os.getenv('LOG_LEVEL', 'INFO'),
                        help="Уровень логирования (DEBUG, INFO, WARNING, ERROR)")
    parser.add_argument('--delay', type=int, default=int(os.getenv('DELAY', 0)),
                        help="Задержка ответа в секундах")
    parser.add_argument('--photo-dir', type=str, default=os.getenv('PHOTO_DIR', 'test_photos'),
                        help="Путь к каталогу с фотографиями")

    return parser.parse_args()

async def archive(request):
    try:
        archive_hash = request.match_info.get('archive_hash')
    except Exception as e:
        return web.Response(status=404, text='Архив не существует или был удален')

    archive_path = os.path.join(args.photo_dir, archive_hash)

    if not os.path.exists(archive_path):
        return web.Response(status=404, text='Архив не существует или был удален')

    response = web.StreamResponse()
    response.headers['Content-Type'] = 'application/zip'
    response.headers['Content-Disposition'] = f'attachment; filename="{archive_hash}.zip"'

    await response.prepare(request)

    command = ['zip', '-r', f'-', f'.']
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=archive_path
    )

    try:
        while True:

            logging.info(u'Sending archive chunk ...')
            chunk = await process.stdout.read(chunk_size_kb * 1024)
            if not chunk:
                break

            await response.write(chunk)
            if args.delay:
                await asyncio.sleep(args.delay)

    except asyncio.CancelledError:
        logging.info('Скачивание прервано, завершение процесса zip...')
        # process.kill()
        # await process.wait()
        # raise

    except RuntimeError:
        logging.error(f'CTRL C: {e}')
        # process.kill()
        await process.wait()
        raise

    except Exception as e:
        logging.error(f'Ошибка при создании архива: {e}')
        await process.wait()
        raise

    finally:
        if process.returncode != 0:
            process.kill()
            error_output = await process.stderr.read()
            raise RuntimeError(f"Ошибка создания архива: {error_output.decode()}")

    return response


async def uptime_handler(request):
    response = web.StreamResponse()
    response.headers['Content-Type'] = 'text/html'
    await response.prepare(request)

    while True:
        formatted_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f'{formatted_date}<br>'  # <br> — HTML тег переноса строки
        await response.write(message.encode('utf-8'))

        await asyncio.sleep(INTERVAL_SECS)


async def handle_index_page(request):
    async with aiofiles.open('index.html', mode='r', encoding='utf-8') as index_file:
        index_contents = await index_file.read()
    return web.Response(text=index_contents, content_type='text/html')


if __name__ == '__main__':
    global args
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), None))
    app = web.Application()
    app.add_routes([
        web.get('/', handle_index_page),
        web.get('/archive/{archive_hash}/', archive),
    ])
    web.run_app(app)
