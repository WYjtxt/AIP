"""Install the platform's native middleware below its selected directory."""
import ctypes
import os
from pathlib import Path
import shlex
import shutil
import socket
import subprocess
import tarfile
import time


SERVICES = ('ai-platform-mysql', 'ai-platform-redis', 'ai-platform-kafka')


def run(args, *, env=None, text=None, check=True, cwd=None):
    result = subprocess.run([str(arg) for arg in args], input=text,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            universal_newlines=True, env=env, cwd=cwd)
    if check and result.returncode:
        raise RuntimeError('%s failed:\n%s' % (args[0], result.stdout[-6000:]))
    return result


def app_directory(package_root, arch):
    package_root = Path(package_root)
    choices = [package_root / arch / 'apps', package_root / 'apps']
    if package_root.name == 'apps':
        choices.insert(0, package_root)
    return next((path for path in choices if path.is_dir()), choices[0])


def medium(apps, *patterns):
    for pattern in patterns:
        paths = sorted(Path(apps).glob(pattern))
        if paths:
            return paths[0]
    raise FileNotFoundError('Missing native installation package: ' + str(Path(apps) / patterns[0]))


def unpack(archive_path, destination):
    """Install an archive with one top directory, retaining that directory."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(str(archive_path), 'r:*') as archive:
        archive.extractall(str(destination))


def install_archive(archive_path, target):
    target = Path(target)
    staging = target.parent / ('.' + target.name + '-install')
    staging.mkdir(parents=True, exist_ok=True)
    unpack(archive_path, staging)
    contents = list(staging.iterdir())
    source = contents[0] if len(contents) == 1 and contents[0].is_dir() else staging
    if source == staging:
        shutil.move(str(staging), str(target))
    else:
        shutil.move(str(source), str(target))
        staging.rmdir()


def write(path, text, mode=0o644):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    path.chmod(mode)


def command_line(*args):
    return ' '.join(shlex.quote(str(arg)) for arg in args)


def unit(name, command, *, user='root', cwd=None, environment=None, after='network.target'):
    settings = ['[Unit]', 'Description=AI Platform ' + name, 'After=' + after,
                '', '[Service]', 'Type=simple', 'User=' + user]
    if cwd:
        settings.append('WorkingDirectory=' + str(cwd))
    for key, value in (environment or {}).items():
        settings.append('Environment="%s=%s"' % (key, str(value).replace('"', '\\"')))
    settings += ['ExecStart=' + command_line(*command), 'Restart=on-failure',
                 'RestartSec=5', 'TimeoutStartSec=120', 'LimitNOFILE=65535',
                 '', '[Install]', 'WantedBy=multi-user.target', '']
    write(Path('/etc/systemd/system') / (name + '.service'), '\n'.join(settings))


def wait_port(port, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=1):
                return
        except OSError:
            time.sleep(1)
    raise RuntimeError('Native middleware did not open port %s' % port)


def install_os_packages(names, package_root, arch, env):
    if not names:
        return
    package_root = Path(package_root)
    os_media = package_root / arch / 'os'
    if not os_media.is_dir():
        os_media = package_root / 'os'
    online = env.get('INSTALL_SOURCE', 'offline') == 'online'
    if shutil.which('dnf'):
        args = ['dnf', '--setopt=install_weak_deps=False']
        if not online:
            repo = os_media / 'repo'
            if not (repo / 'repodata/repomd.xml').is_file():
                raise FileNotFoundError('Missing offline OS repository: ' + str(repo))
            key = os_media / 'RPM-GPG-KEY-openEuler'
            if key.is_file():
                run(['rpm', '--import', key])
            args += ["--disablerepo=*", '--repofrompath=ai-native,file://' + str(repo),
                     '--enablerepo=ai-native']
            if key.is_file():
                args += ['--setopt=ai-native.gpgcheck=1', '--setopt=ai-native.gpgkey=file://' + str(key)]
        run(args + ['install', '-y'] + names)
    else:
        args = ['apt-get', '-y', '--no-remove']
        apt_env = dict(os.environ, DEBIAN_FRONTEND='noninteractive')
        if online:
            run(['apt-get', 'update'], env=apt_env)
        else:
            repo = os_media / 'debs'
            source = os_media / 'native-offline.list'
            write(source, 'deb [trusted=yes] file:%s ./\n' % repo)
            args += ['-o', 'Dir::Etc::sourcelist=' + str(source), '-o',
                     'Dir::Etc::sourceparts=-', '-o', 'Acquire::Retries=0']
            run(args + ['update'], env=apt_env)
        run(args + ['install'] + names, env=apt_env)


def prepare_os(package_root, arch, env):
    dnf = bool(shutil.which('dnf'))
    required = []
    libraries = [('libaio.so.1', 'libaio' if dnf else 'libaio1'),
                 ('libnuma.so.1', 'numactl-libs' if dnf else 'libnuma1'),
                 ('libssl.so.1.1', 'openssl-libs' if dnf else 'libssl1.1'),
                 ('libncurses.so.6', 'ncurses-libs' if dnf else 'libncurses6'),
                 ('libtinfo.so.6', 'ncurses-libs' if dnf else 'libtinfo6')]
    for library, package in libraries:
        try:
            ctypes.CDLL(library)
        except OSError:
            required.append(package)
    for program, package in [('gcc', 'gcc'), ('make', 'make'), ('ar', 'binutils')]:
        if not shutil.which(program):
            required.append(package)
    if not Path('/usr/include/stdio.h').is_file():
        required.append('glibc-devel' if dnf else 'libc6-dev')
    install_os_packages(list(dict.fromkeys(required)), package_root, arch, env)


def sql_literal(value):
    return "'" + value.replace('\\', '\\\\').replace("'", "\\'") + "'"


def initialize_mysql(client, mysql_socket, env):
    password = env['MYSQL_ROOT_PASS']
    def query(sql, supplied):
        return run([client, '--no-defaults', '-uroot', '--socket=' + str(mysql_socket)],
                   env=dict(os.environ, MYSQL_PWD=supplied),
                   text="SET SESSION sql_mode='';\n" + sql, check=False)
    # Do not change an initialized site's password during repair.
    if query('SELECT 1;', '').returncode == 0:
        result = query("ALTER USER 'root'@'localhost' IDENTIFIED WITH caching_sha2_password BY "
                       + sql_literal(password) + ';', '')
        if result.returncode:
            raise RuntimeError('MySQL root initialization failed')
    elif query('SELECT 1;', password).returncode:
        raise RuntimeError('Existing MySQL password rejected; data was preserved')
    admin = env.get('MYSQL_ADMIN_PASS', password)
    sql = ("CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED WITH caching_sha2_password BY "
           + sql_literal(password) + ";\nGRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION;\n"
           "CREATE USER IF NOT EXISTS 'admin'@'%' IDENTIFIED WITH mysql_native_password BY "
           + sql_literal(admin) + ";\nGRANT ALL PRIVILEGES ON *.* TO 'admin'@'%' WITH GRANT OPTION;\n"
           "CREATE DATABASE IF NOT EXISTS seal_system CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;")
    if query(sql, password).returncode:
        raise RuntimeError('MySQL account and database initialization failed')


def install(root, package_root, arch, env):
    root, package_root = Path(root).resolve(), Path(package_root).resolve()
    apps = app_directory(package_root, arch)
    runtime, config = root / 'runtime', root / 'Config_files'
    runtime.mkdir(parents=True, exist_ok=True)
    config.mkdir(parents=True, exist_ok=True)
    prepare_os(package_root, arch, env)

    print('安装/检查原生 MySQL', flush=True)
    mysql_home = runtime / 'mysql'
    if not (mysql_home / 'bin/mysqld').is_file():
        install_archive(medium(apps, 'mysql-8.0.*-linux-glibc2.28-' + arch + '.tar.xz'), mysql_home)
    mysql_data = root / 'mysql'
    mysql_data.mkdir(exist_ok=True)
    mysql_conf, mysql_socket = config / 'mysql.cnf', mysql_data / 'mysql.sock'
    if run(['id', '-u', 'mysql'], check=False).returncode:
        if run(['getent', 'group', 'mysql'], check=False).returncode:
            run(['groupadd', '--system', 'mysql'])
        run(['useradd', '--system', '--gid', 'mysql', '--home-dir', str(mysql_data),
             '--shell', '/sbin/nologin', 'mysql'])
    run(['chown', '-R', 'mysql:mysql', mysql_data])
    mysql_data.chmod(0o750)
    write(mysql_conf, '[mysqld]\nuser=mysql\nbasedir=%s\ndatadir=%s\nsocket=%s\n'
          'pid-file=%s\nlog-error=%s\nport=3306\nbind-address=0.0.0.0\n'
          'lower_case_table_names=1\ncharacter-set-server=utf8mb4\n'
          '[client]\nsocket=%s\n' % (mysql_home, mysql_data, mysql_socket,
          mysql_data / 'mysqld.pid', mysql_data / 'mysqld.log', mysql_socket))
    mysqld = mysql_home / 'bin/mysqld'
    run([mysqld, '--version'])
    if not (mysql_data / 'mysql').is_dir():
        run([mysqld, '--defaults-file=' + str(mysql_conf), '--initialize-insecure', '--user=mysql'])
    unit(SERVICES[0], [mysqld, '--defaults-file=' + str(mysql_conf)], user='mysql')

    print('安装/检查原生 Redis', flush=True)
    redis_home = runtime / 'redis'
    redis_bin = redis_home / 'bin'
    if not (redis_bin / 'redis-server').is_file():
        redis_source = runtime / 'redis-source'
        if not redis_source.is_dir():
            install_archive(medium(apps, 'redis-6.2.14.tar.gz'), redis_source)
        build_env = dict(os.environ)
        build_env.pop('TARGET_ARCH', None)
        run(['make', '-j' + str(min(os.cpu_count() or 2, 8)), 'MALLOC=libc'],
            env=build_env, cwd=redis_source)
        redis_bin.mkdir(parents=True, exist_ok=True)
        for binary in ('redis-server', 'redis-cli', 'redis-benchmark'):
            shutil.copy2(str(redis_source / 'src' / binary), str(redis_bin / binary))
    redis_data = root / 'redis'
    redis_data.mkdir(exist_ok=True)
    redis_conf = config / 'redis.conf'
    if not redis_conf.exists():
        write(redis_conf, 'bind 127.0.0.1\nprotected-mode yes\nport 6379\ndaemonize no\n'
              'dir %s\nappendonly no\nlogfile ""\n' % redis_data)
    unit(SERVICES[1], [redis_bin / 'redis-server', redis_conf], cwd=redis_data)

    print('安装/检查 JDK、Kafka、nginx', flush=True)
    java_home, kafka_home, nginx_home = runtime / 'jdk11', runtime / 'kafka', runtime / 'nginx'
    if not (java_home / 'bin/java').is_file():
        jdk_arch = 'x64' if arch == 'x86_64' else arch
        install_archive(medium(apps, 'microsoft-jdk-11-linux-' + arch + '.tar.gz',
                               'microsoft-jdk-11-linux-' + jdk_arch + '.tar.gz'), java_home)
    if not (kafka_home / 'bin/kafka-server-start.sh').is_file():
        install_archive(medium(apps, 'kafka_2.12-3.6.2.tgz'), kafka_home)
    kafka_data = root / 'kafka/kraft-combined-logs'
    kafka_data.mkdir(parents=True, exist_ok=True)
    kafka_conf = config / 'kafka.properties'
    if not kafka_conf.exists():
        template = (kafka_home / 'config/kraft/server.properties').read_text()
        replacements = {'advertised.listeners': 'PLAINTEXT://' + env.get('TARGET_IP', '127.0.0.1') + ':9092',
                        'log.dirs': str(kafka_data)}
        lines = []
        for line in template.splitlines():
            key = line.split('=', 1)[0]
            lines.append(key + '=' + replacements.pop(key) if key in replacements else line)
        lines += [key + '=' + value for key, value in replacements.items()]
        write(kafka_conf, '\n'.join(lines) + '\n')
    kafka_env = dict(os.environ, JAVA_HOME=str(java_home), LOG_DIR=str(root / 'logs/kafka'),
                     KAFKA_HEAP_OPTS=env.get('KAFKA_HEAP_OPTS', '-Xms256m -Xmx512m'))
    (root / 'logs/kafka').mkdir(parents=True, exist_ok=True)
    if not (kafka_data / 'meta.properties').is_file():
        cluster_id = run([kafka_home / 'bin/kafka-storage.sh', 'random-uuid'], env=kafka_env).stdout.strip()
        run([kafka_home / 'bin/kafka-storage.sh', 'format', '-t', cluster_id, '-c', kafka_conf], env=kafka_env)
    unit(SERVICES[2], [kafka_home / 'bin/kafka-server-start.sh', kafka_conf], cwd=kafka_home,
         environment={key: kafka_env[key] for key in ('JAVA_HOME', 'LOG_DIR', 'KAFKA_HEAP_OPTS')})
    if not (nginx_home / 'sbin/nginx').is_file():
        install_archive(medium(apps, 'opt-nginx.tar.gz'), nginx_home)
    # Prefix-aware startup in deploy_native.py avoids nginx's compiled /opt paths.
    run([nginx_home / 'sbin/nginx', '-V'])
    run(['systemctl', 'daemon-reload'])
    for name, port in zip(SERVICES, (3306, 6379, 9092)):
        run(['systemctl', 'enable', name])
        run(['systemctl', 'restart', name])
        wait_port(port)
        if name == SERVICES[0]:
            initialize_mysql(mysql_home / 'bin/mysql', mysql_socket, env)
    print('NATIVE_MIDDLEWARE=PASS')
    return {'mysql': str(mysql_home / 'bin/mysql'), 'mysqladmin': str(mysql_home / 'bin/mysqladmin'),
            'mysqldump': str(mysql_home / 'bin/mysqldump'), 'mysql_socket': str(mysql_socket),
            'redis': str(redis_bin / 'redis-server'), 'redis_cli': str(redis_bin / 'redis-cli'),
            'nginx': str(nginx_home / 'sbin/nginx'), 'nginx_prefix': str(nginx_home),
            'java': str(java_home / 'bin/java'), 'java_home': str(java_home),
            'kafka': str(kafka_home), 'services': list(SERVICES)}
