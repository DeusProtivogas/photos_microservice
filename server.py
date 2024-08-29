import os
from aiohttp import web
import aiofiles
import asyncio
import datetime
import logging

INTERVAL_SECS = 1
logging.basicConfig(level = logging.DEBUG)
chunk_size_kb = 1


async def archive(request):
    archive_hash = request.match_info.get('archive_hash')
    print(archive_hash)
    archive_path = os.path.join(f'test_photos', archive_hash)

    print(f"Archive path: {archive_path}")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Directory exists: {os.path.exists(archive_path)}")
    print(f"Directory is readable: {os.access(archive_path, os.R_OK)}")

    # archive_path = os.path.abspath(f'test_photos/{archive_hash}')

    if not os.path.exists(archive_path):
        return web.Response(status=404, text='Архив не существует или был удален')

    response = web.StreamResponse()
    response.headers['Content-Type'] = 'application/zip'
    # response.headers['Content-Type'] = 'text/html'
    response.headers['Content-Disposition'] = f'attachment; filename="{archive_hash}.zip"'

    await response.prepare(request)

    command = ['zip', '-r', f'-', f'.']
    print(command)
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
            await asyncio.sleep(2)

    except asyncio.CancelledError:
        logging.info('Скачивание прервано, завершение процесса zip...')
        process.kill()  # Завершение процесса zip
        outs, errs = process.communicate()
        raise

    except RuntimeError:
        logging.error(f'CTRL C: {e}')
        process.kill()
        outs, errs = process.communicate()
        raise

    except Exception as e:
        logging.error(f'Ошибка при создании архива: {e}')
        process.kill()  # Завершение процесса zip
        outs, errs = process.communicate()
        raise

    finally:
        await process.wait()  # Ожидание завершения процесса
        if process.returncode != 0:
            error_output = await process.stderr.read()
            raise RuntimeError(f"Ошибка создания архива: {error_output.decode()}")


    return response


async def uptime_handler(request):
    response = web.StreamResponse()

    # Большинство браузеров не отрисовывают частично загруженный контент, только если это не HTML.
    # Поэтому отправляем клиенту именно HTML, указываем это в Content-Type.
    response.headers['Content-Type'] = 'text/html'

    # Отправляет клиенту HTTP заголовки
    await response.prepare(request)

    while True:
        formatted_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f'{formatted_date}<br>'  # <br> — HTML тег переноса строки

        # Отправляет клиенту очередную порцию ответа
        await response.write(message.encode('utf-8'))

        await asyncio.sleep(INTERVAL_SECS)


async def handle_index_page(request):
    async with aiofiles.open('index.html', mode='r', encoding='utf-8') as index_file:
        index_contents = await index_file.read()
    return web.Response(text=index_contents, content_type='text/html')


if __name__ == '__main__':
    app = web.Application()
    app.add_routes([
        web.get('/', handle_index_page),
        # web.get('/', uptime_handler),
        web.get('/archive/{archive_hash}/', archive),
    ])
    web.run_app(app)
