"""
FastAPI 应用入口
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes_games import router as games_router
from .api.websocket import ws_router

app = FastAPI(
    title="AI 狼人杀",
    description="多智能体协作与博弈系统 — Phase 3",
    version="0.3.0",
)

# CORS: 允许前端开发服务器跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(games_router)
app.include_router(ws_router)


@app.get("/")
async def root():
    return {"name": "AI 狼人杀", "version": "0.3.0", "status": "running"}
