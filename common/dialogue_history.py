import json
import datetime
from typing import List, Dict, Optional, Union
from pydantic import BaseModel, ConfigDict
from sqlalchemy import create_engine, Column, String, Integer, BigInteger, select, func, cast
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import JSON
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.types import TypeDecorator, TEXT, DateTime

from json import JSONEncoder

class CustomJSONEncoder(JSONEncoder):
    '''解决set不能json序列化的问题'''
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        return super().default(obj)

class JSONEncodedDict(TypeDecorator):
    """自定义JSON类型，支持集合等非标准类型"""
    impl = TEXT
    cache_ok = True
    
    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps(value, cls=CustomJSONEncoder, ensure_ascii=False)
    
    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return json.loads(value)

# 使用 pydantic 定义数据模型，启用 ORM 模式
class DialogueRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[int] = None
    timestamp: datetime.datetime  # 改为datetime类型
    user_id: str
    session_id: str
    app_name: str
    invocation_id: str
    agent_name: str
    tag: str
    name: str
    data: Optional[Dict] = None  # JSON 数据

# 基础设置
Base = declarative_base()

# 定义数据库表模型
class DBRecord(Base):
    __tablename__ = 'dialogue_records'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False)  # 改为DateTime类型
    user_id = Column(String, nullable=False)
    session_id = Column(String, nullable=False)
    app_name = Column(String, nullable=False)
    invocation_id = Column(String, nullable=False)
    agent_name = Column(String, nullable=False)
    tag = Column(String, nullable=False)
    name = Column(String, nullable=False)
    data = Column(MutableDict.as_mutable(JSONEncodedDict))  # 使用自定义JSON类型

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

class DialogueHistory:
    def __init__(self, connection_string: str):
        """构造函数，初始化并打开数据库连接"""
        self.connection_string = connection_string
        self.engine = None
        self.session_factory = None

    async def open(self):
        """异步打开数据库连接并创建表（如果表不存在）"""
        self.engine = create_async_engine(self.connection_string)
        self.session_factory = sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        await self.create_tables()

    async def create_tables(self):
        """异步创建表结构"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def append(self, record: DialogueRecord) -> int:
        """异步添加一条对话记录，返回记录ID"""
        async with self.session_factory() as session:
            db_record = DBRecord(
                timestamp=record.timestamp,  # 直接使用datetime对象
                user_id=record.user_id,
                session_id=record.session_id,
                app_name=record.app_name,
                invocation_id=record.invocation_id,
                agent_name=record.agent_name,
                tag=record.tag,
                name=record.name,
                data=record.data
            )
            
            session.add(db_record)
            await session.commit()
            return db_record.id
    
    async def get_by_id(self, record_id: int) -> Optional[DialogueRecord]:
        """异步根据ID获取单条记录"""
        async with self.session_factory() as session:
            result = await session.get(DBRecord, record_id)
            return DialogueRecord.model_validate(result) if result else None
    
    async def get_by_invocation_id(self, invocation_id: str) -> Optional[DialogueRecord]:
        """根据调用ID获取单条记录"""
        async with self.session_factory() as session:
            stmt = select(DBRecord).where(DBRecord.invocation_id == invocation_id)
            result = await session.execute(stmt)
            return DialogueRecord.model_validate(result.scalar_one_or_none()) if result.scalar_one_or_none() else None
    
    async def get_by_user(self, user_id: str, limit: int = 100) -> List[DialogueRecord]:
        """获取指定用户的对话记录"""
        async with self.session_factory() as session:
            stmt = select(DBRecord).where(DBRecord.user_id == user_id).order_by(DBRecord.timestamp.desc()).limit(limit)
            result = await session.execute(stmt)
            return [DialogueRecord.model_validate(r) for r in result.scalars().all()]
    
    async def get_by_session(self, session_id: str, limit: int = 100) -> List[DialogueRecord]:
        """获取指定会话的对话记录"""
        async with self.session_factory() as session:
            stmt = select(DBRecord).where(DBRecord.session_id == session_id).order_by(DBRecord.timestamp.asc()).limit(limit)
            result = await session.execute(stmt)
            return [DialogueRecord.model_validate(r) for r in result.scalars().all()]
    
    async def get_by_tag(self, tag: str, limit: int = 100) -> List[DialogueRecord]:
        """获取指定标签的对话记录"""
        async with self.session_factory() as session:
            stmt = select(DBRecord).where(DBRecord.tag == tag).order_by(DBRecord.timestamp.desc()).limit(limit)
            result = await session.execute(stmt)
            return [DialogueRecord.model_validate(r) for r in result.scalars().all()]
    
    async def search_by_keyword(self, keyword: str, limit: int = 100) -> List[DialogueRecord]:
        """在内容中搜索关键词"""
        async with self.session_factory() as session:
            # 使用通用的 JSON 搜索方法
            search_expr = (
                DBRecord.name.ilike(f'%{keyword}%') |
                cast(DBRecord.data, String).ilike(f'%{keyword}%')
            )
            
            stmt = select(DBRecord).where(search_expr).order_by(DBRecord.timestamp.desc()).limit(limit)
            result = await session.execute(stmt)
            return [DialogueRecord.model_validate(r) for r in result.scalars().all()]

    async def close(self):
        """异步关闭数据库连接"""
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            self.session_factory = None

# 使用示例
async def example_usage():
    # 选择数据库连接 (SQLite 或 PostgreSQL)
    DB_URI = "sqlite+aiosqlite:///dialogue_history.db"  # SQLite
    # DB_URI = "postgresql://user:password@localhost:5432/dialogue_db"  # PostgreSQL
    
    # 初始化
    db = DialogueHistory(DB_URI)
    
    # 打开连接
    await db.open()
    
    # 创建一条记录
    record = DialogueRecord(
        timestamp=datetime.datetime.now(),  # 修正为datetime对象
        user_id="user123",
        session_id="session456",
        app_name="chatbot",
        invocation_id="invocation789",
        agent_name="assistant",
        tag="greeting",
        name="用户打招呼",
        data={
            "message": "你好",
            "intent": "greeting",
            "response": "欢迎使用我们的服务！"
        }
    )
    
    # 添加记录
    record_id = await db.append(record)
    print(f"添加记录，ID: {record_id}")
    
    # 查询用户对话
    user_records = await db.get_by_user("user123")
    for r in user_records:
        print(f"用户记录: {r.name}, 时间: {r.timestamp}")
    
    # 关键词搜索
    search_results = await db.search_by_keyword("服务")
    print(f"搜索结果数量: {len(search_results)}")
    
    # 关闭连接
    await db.close()

# 如果你需要直接运行此脚本进行测试
if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())