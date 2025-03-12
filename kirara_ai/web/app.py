import asyncio
import mimetypes
import os
import socket
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from hypercorn.asyncio import serve
from hypercorn.config import Config
from quart import Quart, g, jsonify

from kirara_ai.config.global_config import GlobalConfig
from kirara_ai.ioc.container import DependencyContainer
from kirara_ai.logger import HypercornLoggerWrapper, get_logger
from kirara_ai.web.auth.services import AuthService, FileBasedAuthService

from .api.block import block_bp
from .api.dispatch import dispatch_bp
from .api.im import im_bp
from .api.llm import llm_bp
from .api.plugin import plugin_bp
from .api.system import system_bp
from .api.workflow import workflow_bp
from .auth.routes import auth_bp

ERROR_MESSAGE = """
<h1>WebUI launch failed!</h1>
<p lang="en">Web UI not found. Please download from <a href='https://github.com/DarkSkyTeam/chatgpt-for-bot-webui/releases' target='_blank'>here</a> and extract to the <span>TARGET_DIR</span> folder, make sure the <span>TARGET_DIR/index.html</span> file exists.</p>
<h1>WebUI 启动失败！</h1>
<p lang="zh-CN">Web UI 未找到。请从 <a href='https://github.com/DarkSkyTeam/chatgpt-for-bot-webui/releases' target='_blank'>这里</a> 下载并解压到 <span>TARGET_DIR</span> 文件夹，确保 <span>TARGET_DIR/index.html</span> 文件存在。</p>

<style>
    body {
        font-family: Arial, sans-serif;
        background-color: #f0f0f0;
        color: #333;
        padding: 20px;
    }
    h1 {
        color: #333;
        font-size: 24px;
        margin-bottom: 10px;
    }
    p {
        font-size: 16px;
        margin-bottom: 10px;
    }
    a {
        color: #007bff;
        text-decoration: none;
    }
</style>
"""


cwd = os.getcwd()
STATIC_FOLDER = f"{cwd}/web"

logger = get_logger("WebServer")

custom_static_assets = {}

def create_web_api_app(container: DependencyContainer) -> Quart:
    """创建 Web API 应用（Quart）"""
    app = Quart(__name__, static_folder=STATIC_FOLDER)
    app.json.sort_keys = False
    
    # 注册蓝图
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(im_bp, url_prefix="/api/im")
    app.register_blueprint(llm_bp, url_prefix="/api/llm")
    app.register_blueprint(dispatch_bp, url_prefix="/api/dispatch")
    app.register_blueprint(block_bp, url_prefix="/api/block")
    app.register_blueprint(workflow_bp, url_prefix="/api/workflow")
    app.register_blueprint(plugin_bp, url_prefix="/api/plugin")
    app.register_blueprint(system_bp, url_prefix="/api/system")
    
    @app.errorhandler(Exception)
    def handle_exception(error):
        logger.opt(exception=error).error("Error during request")
        response = jsonify({"error": str(error)})
        response.status_code = 500
        return response

    # 在每个请求前将容器注入到上下文
    @app.before_request
    async def inject_container():
        g.container = container

    app.container = container
    
    return app

def create_app(container: DependencyContainer) -> FastAPI:
    """创建主应用（FastAPI）"""
    app = FastAPI()
    
    # 配置 CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 强制设置 MIME 类型
    mimetypes.add_type("text/html", ".html")
    mimetypes.add_type("text/css", ".css")
    mimetypes.add_type("text/javascript", ".js")
    mimetypes.add_type("image/svg+xml", ".svg")
    mimetypes.add_type("image/png", ".png")
    mimetypes.add_type("image/jpeg", ".jpg")
    mimetypes.add_type("image/gif", ".gif")
    mimetypes.add_type("image/webp", ".webp")
    
    
    # 自定义静态资源处理
    async def serve_custom_static(path: str):
        if path not in custom_static_assets:
            raise HTTPException(status_code=404, detail="File not found")
        return FileResponse(custom_static_assets[path])
    
    @app.get("/", response_class=HTMLResponse)
    async def index():
        try:
            index_path = Path(STATIC_FOLDER) / "index.html"
            if not index_path.exists():
                return HTMLResponse(content=ERROR_MESSAGE.replace("TARGET_DIR", STATIC_FOLDER))
            return FileResponse(index_path)
        except Exception as e:
            logger.error(f"Error serving index: {e}")
            return HTMLResponse(content=ERROR_MESSAGE.replace("TARGET_DIR", STATIC_FOLDER))

    @app.middleware("http")
    async def spa_middleware(request: Request, call_next):
        path = request.url.path
        skip_paths = [route.path for route in app.routes]
        skip_paths.remove("/")
        
        # 处理自定义静态资源
        if path in custom_static_assets:
            return await serve_custom_static(path)
        
        # 如果路径以 backend-api 开头，交由内置路由处理
        if any(path.startswith(skip_path) for skip_path in skip_paths):
            return await call_next(request)

        try:
            file_path = Path(STATIC_FOLDER) / path.lstrip('/')
            # 检查路径穿越
            if not file_path.resolve().is_relative_to(Path(STATIC_FOLDER).resolve()):
                raise HTTPException(status_code=404, detail="Access denied")
            
            # 如果文件存在，返回文件
            if file_path.is_file():
                return FileResponse(file_path)
                
            # 否则返回 index.html（SPA 路由）
            return FileResponse(Path(STATIC_FOLDER) / "index.html")
            
        except Exception as e:
            logger.error(f"Error serving static file {path}: {e}")
            return FileResponse(Path(STATIC_FOLDER) / "index.html")
    
    return app


class WebServer:
    app: FastAPI
    web_api_app: Quart
    
    def __init__(self, container: DependencyContainer):
        self.app = create_app(container)
        self.web_api_app = create_web_api_app(container)
        self.server_task = None
        self.shutdown_event = asyncio.Event()
        container.register(
            AuthService,
            FileBasedAuthService(
                password_file=Path(container.resolve(GlobalConfig).web.password_file),
                secret_key=container.resolve(GlobalConfig).web.secret_key,
            ),
        )
        self.config = container.resolve(GlobalConfig)

        # 配置 hypercorn
        from hypercorn.logging import Logger

        self.hypercorn_config = Config()
        self.hypercorn_config.bind = [f"{self.config.web.host}:{self.config.web.port}"]
        self.hypercorn_config._log = Logger(self.hypercorn_config)
        
        # 创建自定义的日志包装器，添加 URL 过滤
        class FilteredLoggerWrapper(HypercornLoggerWrapper):
            def info(self, message, *args, **kwargs):
                # 过滤掉不需要记录的URL请求日志
                ignored_paths = [
                    '/backend-api/api/system/status',  # 添加需要过滤的URL路径
                    '/favicon.ico',
                ]
                for path in ignored_paths:
                    if path in str(args):
                        return
                super().info(message, *args, **kwargs)
        
        # 使用新的过滤日志包装器
        self.hypercorn_config._log.access_logger = FilteredLoggerWrapper(logger)
        self.hypercorn_config._log.error_logger = HypercornLoggerWrapper(logger)
        
        # 挂载 Web API 应用
        self.mount_app("/backend-api", self.web_api_app)

    def mount_app(self, prefix: str, app):
        """挂载子应用到指定路径前缀"""
        self.app.mount(prefix, app)

    def _check_port_available(self, host: str, port: int) -> bool:
        """检查端口是否可用"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
                return True
            except socket.error:
                return False

    async def start(self):
        """启动Web服务器"""
        # 检查端口是否被占用
        if not self._check_port_available(self.config.web.host, self.config.web.port):
            error_msg = f"端口 {self.config.web.port} 已被占用，无法启动服务器，请修改端口或关闭其他占用端口的程序。"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
            
        self.server_task = asyncio.create_task(serve(self.app, self.hypercorn_config, shutdown_trigger=self.shutdown_event.wait))
        logger.info(
            f"监听地址：http://{self.config.web.host}:{self.config.web.port}/"
        )

    async def stop(self):
        """停止Web服务器"""
        self.shutdown_event.set()
        
        if self.server_task:
            try:
                await self.server_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Error during server shutdown: {e}")

    def add_static_assets(self, url_path: str, local_path: str):
        custom_static_assets[url_path] = local_path
