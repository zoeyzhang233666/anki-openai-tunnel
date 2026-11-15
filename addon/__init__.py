"""Anki companion for the official OpenAI tunnel-client (Windows / macOS)."""
import json
from pathlib import Path
import urllib.request
import webbrowser

from aqt import mw
from aqt.qt import (QAction, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                    QInputDialog, QLineEdit, QProcess, QProcessEnvironment, QTimer)
from aqt.utils import showInfo, showWarning
from .core import health_url, private_json, profile, redact, validate

STATE = Path(__file__).resolve().parent / 'user_files'


class Tunnel:
    def __init__(self):
        self.process = None
        self.stage = ''
        self.tail = ''
        self.buffer = b''
        self.secret = ''
        self.active_config = None
        mw.app.aboutToQuit.connect(self.shutdown)

    def running(self):
        return self.process is not None and self.process.state() != QProcess.ProcessState.NotRunning

    def settings(self):
        if self.running():
            showInfo('请先停止本插件启动的连接，再修改设置。')
            return
        config = mw.addonManager.getConfig(__name__) or {}
        dialog = QDialog(mw)
        dialog.setWindowTitle('OpenAI 隧道设置')
        layout = QFormLayout(dialog)
        fields = {}
        for name, label in [('binary', '官方 tunnel-client 路径'), ('tunnel_id', '已有 Tunnel ID'),
                            ('organization_id', 'Platform Organization ID（可选）'),
                            ('mcp_url', '本机 AnkiMCP 地址')]:
            field = QLineEdit(str(config.get(name, '')), dialog)
            fields[name] = field
            layout.addRow(label, field)
        browse = QDialogButtonBox(QDialogButtonBox.StandardButton.Open, dialog)
        def choose():
            filename, _ = QFileDialog.getOpenFileName(dialog, '选择官方 tunnel-client 可执行文件')
            if filename:
                fields['binary'].setText(filename)
        browse.clicked.connect(choose)
        layout.addRow('选择程序', browse)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                config = validate({k: v.text().strip() for k, v in fields.items()})
            except ValueError as exc:
                showWarning(str(exc))
                return
            mw.addonManager.writeConfig(__name__, config)
            showInfo('设置已保存。API Key 不保存在设置中。')

    def start(self):
        if self.running():
            showInfo('本插件已有连接操作正在运行。请用“查看状态”检查。')
            return
        try:
            config = validate(mw.addonManager.getConfig(__name__) or {})
        except ValueError as exc:
            showWarning(str(exc))
            return
        key, ok = QInputDialog.getText(mw, '启动已有 OpenAI 隧道',
            '输入现有 Runtime API Key（仅本次内存使用）。\n同一 Tunnel ID 请先停止其他电脑/旧插件的客户端。',
            QLineEdit.EchoMode.Password)
        if not ok:
            return
        key = key.strip()
        if not key or any(c.isspace() for c in key):
            showWarning('密钥为空或包含空白字符。')
            return
        self.secret = key
        self.tail = ''
        self.active_config = config
        private_json(STATE / 'runtime.json', profile(config, STATE / 'health.url'))
        (STATE / 'health.url').unlink(missing_ok=True)
        self.launch('doctor')

    def launch(self, stage):
        self.stage = stage
        self.buffer = b''
        process = QProcess(mw)
        self.process = process
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        environment = QProcessEnvironment.systemEnvironment()
        for name in ('OPENAI_API_KEY', 'OPENAI_ADMIN_KEY'):
            environment.remove(name)
        environment.insert('CONTROL_PLANE_API_KEY', self.secret)
        if self.active_config['organization_id']:
            environment.insert('CONTROL_PLANE_ORGANIZATION_ID', self.active_config['organization_id'])
        else:
            environment.remove('CONTROL_PLANE_ORGANIZATION_ID')
        process.setProcessEnvironment(environment)
        process.readyReadStandardOutput.connect(lambda: self.output(process))
        process.finished.connect(lambda code, status: self.finished(process, stage, code, status))
        process.errorOccurred.connect(lambda error: self.error(process, error))
        args = [stage, '--profile-file', str(STATE / 'runtime.json')]
        if stage == 'doctor':
            args.append('--explain')
        process.start(self.active_config['binary'], args)
        if stage == 'doctor':
            QTimer.singleShot(65000, lambda: self.doctor_timeout(process))

    def doctor_timeout(self, process):
        if process is self.process and self.stage == 'doctor' and self.running():
            self.shutdown()
            showWarning('doctor 超时，已停止本次检查；未启动隧道。')

    def output(self, process):
        # Buffer full lines before sanitizing so a secret split across chunks cannot leak.
        self.buffer += bytes(process.readAllStandardOutput())
        lines = self.buffer.split(b'\n')
        self.buffer = lines.pop()
        if len(self.buffer) > 1048576:
            self.buffer = b''  # Drop oversized partial lines; never emit unredacted content.
        for line in lines:
            self.tail = (self.tail + redact(line.decode('utf-8', errors='replace'), self.secret) + '\n')[-12000:]

    def finished(self, process, stage, code, status):
        self.output(process)
        if self.buffer:
            self.tail = (self.tail + redact(self.buffer.decode('utf-8', errors='replace'), self.secret))[-12000:]
            self.buffer = b''
        if process is not self.process:
            process.deleteLater()
            return
        self.process = None
        process.setProcessEnvironment(QProcessEnvironment())
        process.deleteLater()
        if stage == 'doctor' and code == 0 and status == QProcess.ExitStatus.NormalExit:
            self.launch('run')
            return
        self.secret = ''
        if stage == 'doctor':
            showWarning('doctor 未通过，未启动隧道。\n' + self.tail[-5000:])
        elif stage == 'run' and code != 0:
            showWarning('隧道已退出。\n' + self.tail[-5000:])

    def error(self, process, error):
        if process is self.process and error == QProcess.ProcessError.FailedToStart:
            self.process = None
            process.setProcessEnvironment(QProcessEnvironment())
            process.deleteLater()
            self.secret = ''
            showWarning('无法启动 tunnel-client；请检查系统版本、程序路径及操作系统安全提示。')

    def stop(self):
        self.stage = 'stopping'
        self.shutdown()
        showInfo('已停止本插件拥有的连接。')

    def shutdown(self):
        process = self.process
        self.process = None  # Prevent doctor completion from launching run during shutdown.
        if process:
            process.terminate()
            if not process.waitForFinished(3000):
                process.kill()
                process.waitForFinished(2000)
            process.setProcessEnvironment(QProcessEnvironment())
            process.deleteLater()
        self.secret = ''
        self.buffer = b''

    def status(self):
        if not self.running():
            showInfo('本插件没有运行中的客户端。' + ('\n最近输出：\n' + self.tail[-3500:] if self.tail else ''))
            return
        if self.stage == 'doctor':
            showInfo('正在运行 doctor；检查通过后自动启动连接。')
            return
        def task():
            url = health_url(STATE / 'health.url')
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(url + '/health?details=true', timeout=4) as response:
                return json.load(response)
        def done(future):
            try:
                health = future.result()
                control = health.get('components', {}).get('control-plane', {})
                detail = control.get('details', {})
                showInfo('Ready: %s\nOpenAI 轮询: %s\n最近成功: %s\n\n最终可用性请在 ChatGPT 普通聊天执行 list_decks 验证。' %
                         (health.get('ready'), control.get('state'), detail.get('last_success', '未观察到')))
            except Exception:
                showInfo('客户端正在启动或健康接口暂不可用。\n' + self.tail[-3500:])
        mw.taskman.run_in_background(task, done)

    def ui(self):
        try:
            if not self.running() or self.stage != 'run':
                raise ValueError()
            webbrowser.open(health_url(STATE / 'health.url') + '/ui')
        except (OSError, ValueError):
            showInfo('请先启动连接，等待健康地址生成。')


controller = Tunnel()
menu = mw.form.menuTools.addMenu('OpenAI 隧道连接')
for label, callback in [('设置', controller.settings), ('启动连接', controller.start),
                        ('查看状态', controller.status), ('打开管理界面', controller.ui),
                        ('停止连接', controller.stop)]:
    action = QAction(label, mw)
    action.triggered.connect(lambda checked=False, cb=callback: cb())
    menu.addAction(action)
