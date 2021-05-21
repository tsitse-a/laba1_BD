#laba done by students Elizarov, Tsitserovskaya, Shadrin
#virtual machines can be downloaded from the link https://drive.google.com/drive/folders/1K0QvTZ1A7ruCExIh73Gt_21JC66Ifdrg?usp=sharing

import asyncio
from asyncio import subprocess
from datetime import datetime, timedelta

import aiopg
from aiohttp import ClientSession, ClientTimeout, web


def load_config() -> dict:
    config: dict = {
        'MODE': 'AGENT',
        'DATABASE_DSN': None,
        'AGENT_ADDRESSES': [],
    }

    try:
        import config as config_file

        if config_file.MODE == 'AGENT' and config_file.AGENT_ADDRESSES:
            config['MODE'] = config_file.MODE
            config['AGENT_ADDRESSES'] = config_file.AGENT_ADDRESSES
        elif config_file.MODE == 'DATABASE' and config_file.DATABASE_ADDRESS and config_file.DATABASE_CRED:
            config['MODE'] = config_file.MODE
            database_data = {
                'dbname': config_file.DATABASE_ADDRESS[2],
                'user': config_file.DATABASE_CRED[0],
                'password': config_file.DATABASE_CRED[1],
                'host': config_file.DATABASE_ADDRESS[0],
                'port': config_file.DATABASE_ADDRESS[1],
            }
            config['DATABASE_DSN'] = ' '.join(f'{value[0]}={value[1]}' for value in database_data.items())
        else:
            print('cant apply config')
    except:
        print('cant load config')

    print('load config success')
    return config


async def start_background_tasks(app):
    if app['config']['MODE'] == 'AGENT':
        async def ping(app):
            async with ClientSession(timeout=ClientTimeout(1)) as session:
                while True:
                    await asyncio.sleep(1)
                    for agent_address in app['config']['AGENT_ADDRESSES']:
                        try:
                            async with session.get(f'{agent_address}/ping') as resp:
                                if resp.status != 200:
                                    print(f'{agent_address} got {resp.status} error')
                                else:
                                    print(f'{agent_address} available')
                        except:
                            print(f'{agent_address} unavailable')

        app['ping'] = asyncio.create_task(ping(app))
        print('AGENT ping task created')
    elif app['config']['MODE'] == 'DATABASE':
        async def check_database(app):
            async with aiopg.create_pool(app['config']['DATABASE_DSN']) as pool:
                async with pool.acquire() as conn:
                    # DETECT DB ROLE
                    app['state']['database_role'] = 'SINGLE'
                    async with conn.cursor() as cur:
                        await cur.execute('SELECT state FROM pg_catalog.pg_stat_replication')
                        ret = []
                        async for row in cur:
                            ret.append(row)
                        if ret:
                            app['state']['database_role'] = 'MASTER'
                    async with conn.cursor() as cur:
                        await cur.execute('SELECT status FROM pg_catalog.pg_stat_wal_receiver')
                        ret = []
                        async for row in cur:
                            ret.append(row)
                        if ret:
                            app['state']['database_role'] = 'SLAVE'
                    print(f'database role {app["state"]["database_role"]}')
                    if app['state']['database_role'] == 'SINGLE':
                        print('SINGLE database role. exit.')
                        exit(0)
                    while True:
                        await asyncio.sleep(10)
                        is_available = True
                        if app['state']['database_role'] == 'MASTER':
                            try:
                                async with conn.cursor() as cur:
                                    await cur.execute('SELECT state FROM pg_catalog.pg_stat_replication')
                                    ret = []
                                    async for row in cur:
                                        ret.append(row)
                                    if not ret or ret[0][0] != 'streaming':
                                        is_available = False
                            except:
                                is_available = False
                        else:
                            try:
                                async with conn.cursor() as cur:
                                    await cur.execute('SELECT status FROM pg_catalog.pg_stat_wal_receiver')
                                    ret = []
                                    async for row in cur:
                                        ret.append(row)
                                    if not ret or ret[0][0] != 'streaming':
                                        is_available = False
                            except:
                                is_available = False

                        print(f'database is available - {is_available}')
                        agent_available = app['state']['last_witness_access'] >= datetime.now() - timedelta(seconds=10)
                        print(f'agent is available - {agent_available}')

                        if app['state']['database_role'] == 'MASTER':
                            if not is_available and not agent_available:
                                # slave database is unavailable and last agent is unavailable.
                                print('shutdown MASTER and exit')
                                print('service postgresql stop')
                                await subprocess.create_subprocess_shell('service postgresql stop')
                                exit(0)
                        else:
                            if not is_available and agent_available:
                                # master database is unavailable and last agent is available.
                                print('promote SLAVE to MASTER and exit')
                                print('sudo -u postgres /usr/lib/postgresql/12/bin/pg_ctl promote -D /var/lib/postgresql/12/main')
                                await subprocess.create_subprocess_shell('sudo -u postgres /usr/lib/postgresql/12/bin/pg_ctl promote -D /var/lib/postgresql/12/main')
                                exit(0)

        app['check_database'] = asyncio.create_task(check_database(app))


async def cleanup_background_tasks(app):
    if app['config']['MODE'] == 'AGENT':
        app['ping'].cancel()
        await app['ping']
    elif app['config']['MODE'] == 'DATABASE':
        app['check_database'].cancel()
        await app['check_database']


if __name__ == '__main__':
    app = web.Application()
    app['config']: dict = load_config()
    app['state']: dict = {
        'last_witness_access': datetime.now(),
        'database_status': True,
        'database_role': None,
    }

    print(f'mode {app["config"]["MODE"]}')

    if app['config']['MODE'] == 'DATABASE':
        async def ping(request):
            request.app['state']['last_witness_access'] = datetime.now()

            if request.app['state']['database_status']:
                return web.HTTPOk()

            return web.HTTPServiceUnavailable()


        app.add_routes([
            web.get('/ping', ping),
        ])

    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)

    web.run_app(app, host='0.0.0.0', port=8080)
