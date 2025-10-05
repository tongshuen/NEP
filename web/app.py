from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from storage.base import BaseStorage

def create_app(config: Dict[str, Any], storage: BaseStorage):
    """创建Web应用"""
    app = FastAPI(title="NEP Web Admin")
    templates = Jinja2Templates(directory="templates")
    
    # 挂载静态文件
    app.mount("/static", StaticFiles(directory="static"), name="static")
    
    # 添加路由
    from web import routes
    routes.setup_routes(app, templates, storage)
    
    return app
