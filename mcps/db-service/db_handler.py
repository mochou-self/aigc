"""
此模块实现了基于 SQLite3 的数据库操作功能。
支持列出表、描述表结构、读取数据、写入数据和创建表等操作。
"""
import logging
from typing import List, Dict, Any
from sqlalchemy import create_engine, inspect, MetaData, Table, Column, String, Integer, Boolean, Text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from pathlib import Path

# 配置日志记录
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('db')

# 定义工具列表
TOOLS = [
    {
        'name': 'list_tables',
        'description': '列出数据库中的所有表',
        'input_schema': {'type': 'object'}
    },
    {
        'name': 'describe_table',
        'description': '描述指定表的结构',
        'input_schema': {
            'type': 'object',
            'properties': {
                'table_name': {'type': 'string'}
            },
            'required': ['table_name']
        }
    },
    {
        'name': 'read_data',
        'description': '从指定表中读取数据',
        'input_schema': {
            'type': 'object',
            'properties': {
                'table_name': {'type': 'string'},
                'limit': {'type': 'integer', 'default': 10}
            },
            'required': ['table_name']
        }
    },
    {
        'name': 'write_data',
        'description': '向指定表中写入数据',
        'input_schema': {
            'type': 'object',
            'properties': {
                'table_name': {'type': 'string'},
                'data': {'type': 'object'}
            },
            'required': ['table_name', 'data']
        }
    },
    {
        'name': 'create_table',
        'description': '创建新表，严格控制表字段属性',
        'input_schema': {
            'type': 'object',
            'properties': {
                'table_name': {'type': 'string'},
                'columns': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'name': {'type': 'string'},
                            'type': {'type': 'string', 'enum': ['str', 'int', 'bool', 'text']},
                            'nullable': {'type': 'boolean', 'default': True},
                            'unique': {'type': 'boolean', 'default': False},
                            'primary_key': {'type': 'boolean', 'default': False},
                            'description': {'type': 'string'}
                        },
                        'required': ['name', 'type']
                    }
                }
            },
            'required': ['table_name', 'columns']
        }
    }
]

def get_session(db_url: str):
    """
    获取数据库会话

    :param db_url: 数据库连接 URL
    :return: 数据库会话类
    """
    engine = create_engine(db_url)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 列出所有表
def list_tables(engine) -> List[str]:
    """
    列出数据库中的所有表

    :param engine: 数据库引擎
    :return: 表名列表
    """
    inspector = inspect(engine)
    return inspector.get_table_names()

# 描述表结构
def describe_table(engine, table_name: str) -> List[Dict[str, Any]]:
    """
    描述指定表的结构

    :param engine: 数据库引擎
    :param table_name: 表名
    :return: 表结构信息列表
    """
    inspector = inspect(engine)
    return inspector.get_columns(table_name)

# 读取数据
def read_data(session_maker, table_name: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    从指定表中读取数据

    :param session_maker: 数据库会话类
    :param table_name: 表名
    :param limit: 读取数据的数量限制，默认为 10
    :return: 数据列表
    """
    session = session_maker()
    try:
        result = session.execute(f"SELECT * FROM {table_name} LIMIT {limit}")
        columns = result.keys()
        return [dict(zip(columns, row)) for row in result.fetchall()]
    except Exception as e:
        logger.error(f'读取数据失败: {str(e)}')
        raise
    finally:
        session.close()

# 写入数据
def write_data(session_maker, table_name: str, data: Dict[str, Any]) -> None:
    """
    向指定表中写入数据

    :param session_maker: 数据库会话类
    :param table_name: 表名
    :param data: 要写入的数据
    """
    session = session_maker()
    try:
        columns = ', '.join(data.keys())
        placeholders = ', '.join([':' + key for key in data.keys()])
        session.execute(
            f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})",
            data
        )
        session.commit()
    except Exception as e:
        logger.error(f'写入数据失败: {str(e)}')
        session.rollback()
        raise
    finally:
        session.close()

# 创建表
def create_table(engine, table_name: str, columns: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    创建新表

    :param engine: 数据库引擎
    :param table_name: 表名
    :param columns: 字段配置列表，每个字段包含以下键：
        - name: 字段名
        - type: 字段类型 (str, int, bool, text)
        - nullable: 是否可以为 NULL (bool)
        - unique: 是否唯一 (bool)
        - primary_key: 是否为主键 (bool)
        - description: 字段描述
    :return: 操作结果
    """
    try:
        inspector = inspect(engine)
        if table_name in inspector.get_table_names():
            return {"status": "error", "message": f"表 {table_name} 已存在"}

        metadata = MetaData()
        column_objects = []
        for col in columns:
            # 映射字段类型
            if col['type'] == 'str':
                col_type = String()
            elif col['type'] == 'int':
                col_type = Integer()
            elif col['type'] == 'bool':
                col_type = Boolean()
            elif col['type'] == 'text':
                col_type = Text()
            else:
                return {"status": "error", "message": f"不支持的字段类型 {col['type']}"}

            column_objects.append(
                Column(
                    col['name'],
                    col_type,
                    nullable=col.get('nullable', True),
                    unique=col.get('unique', False),
                    primary_key=col.get('primary_key', False)
                )
            )

        # 创建表
        Table(table_name, metadata, *column_objects)
        metadata.create_all(engine)
        logger.info(f"成功创建表 {table_name}")
        return {"status": "success", "message": f"表 {table_name} 创建成功"}
    except SQLAlchemyError as e:
        logger.error(f"创建表 {table_name} 失败: {str(e)}")
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(f"创建表 {table_name} 时发生意外错误: {str(e)}")
        return {"status": "error", "message": str(e)}

