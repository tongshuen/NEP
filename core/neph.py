import logging
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from utils.auth import authenticate_web
from utils.converter import nep_to_http, http_to_nep
from models.mail import EmailMessage

logger = logging.getLogger(__name__)

class NEPServer:
    """NEP-H服务器，基于HTTP协议"""
    
    def __init__(self, config: Dict[str, Any], storage):
        self.config = config
        self.storage = storage
        self.app = FastAPI(title="NEP-H Server")
        self.templates = Jinja2Templates(directory="web/templates")
        
        self._setup_routes()
        self._mount_static()

    def _setup_routes(self):
        """设置路由"""
        # Web界面
        self.app.get("/", response_class=HTMLResponse)(self.web_index)
        self.app.get("/inbox", response_class=HTMLResponse)(self.web_inbox)
        self.app.get("/compose", response_class=HTMLResponse)(self.web_compose)
        
        # API端点
        self.app.post("/api/auth")(self.api_auth)
        self.app.get("/api/mails")(self.api_list_mails)
        self.app.get("/api/mails/{mail_id}")(self.api_get_mail)
        self.app.post("/api/mails")(self.api_send_mail)
        self.app.put("/api/mails/{mail_id}")(self.api_update_mail)
        
        # 用户管理
        self.app.post("/api/users")(self.api_create_user)
        self.app.delete("/api/users/{user_id}")(self.api_delete_user)

    def _mount_static(self):
        """挂载静态文件"""
        self.app.mount("/static", StaticFiles(directory="web/static"), name="static")

    async def web_index(self, request: Request):
        """首页"""
        return self.templates.TemplateResponse("index.html", {"request": request})

    async def web_inbox(self, request: Request):
        """收件箱页面"""
        # 检查认证
        session = await authenticate_web(request)
        if not session:
            raise HTTPException(status_code=401, detail="Unauthorized")
            
        # 获取邮件列表
        emails = await self.storage.list_emails(session['email'], 'INBOX', 50, 0)
        
        return self.templates.TemplateResponse(
            "inbox.html",
            {
                "request": request,
                "emails": [email.to_dict() for email in emails]
            }
        )

    async def api_auth(self, request: Request):
        """API认证"""
        data = await request.json()
        session = await authenticate_web(data)
        if not session:
            raise HTTPException(status_code=401, detail="Authentication failed")
            
        return JSONResponse({"status": "ok", "session_id": session['session_id']})

    async def api_list_mails(self, request: Request, mailbox: str = "INBOX", limit: int = 50, offset: int = 0):
        """列出邮件API"""
        session = await authenticate_web(request)
        if not session:
            raise HTTPException(status_code=401, detail="Unauthorized")
            
        emails = await self.storage.list_emails(session['email'], mailbox, limit, offset)
        return JSONResponse({
            "status": "ok",
            "emails": [email.to_dict() for email in emails]
        })

    async def api_send_mail(self, request: Request):
        """发送邮件API"""
        session = await authenticate_web(request)
        if not session:
            raise HTTPException(status_code=401, detail="Unauthorized")
            
        data = await request.json()
        
        # 转换为NEP邮件格式
        nep_email = http_to_nep(data, session['email'])
        
        # 存储邮件
        try:
            await self.storage.store_email(nep_email)
            return JSONResponse({"status": "ok", "message_id": nep_email.message_id})
        except Exception as e:
            logger.error(f"Error storing email: {e}")
            raise HTTPException(status_code=500, detail="Failed to send email")

    async def start(self):
        """启动NEP-H服务器"""
        import uvicorn
        uvicorn.run(
            self.app,
            host=self.config['host'],
            port=self.config['port'],
            log_level="info"
        )
