"""
SkillQuest AI 答疑知识库种子（模块6）

为演示环境预置若干篇与技能图谱关联的示例文档，使聊天答疑开箱即用：
上传即切分 + 规则向量化，会话可直接检索出引用。
"""

from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chat import KnowledgeDocument
from app.models.skill import SkillNode
from app.services.rag import index_document

# (标题, 关联技能名, 来源, 正文) —— 正文应能覆盖技能图谱知识点
_DOCS: List[Dict[str, str]] = [
    {
        "title": "Python 编程基础速查",
        "skill": "Python 基础",
        "source": "技能图谱配套课程",
        "content": (
            "Python 是一种解释型、面向对象的高级编程语言，语法简洁，适合快速开发。"
            "基础语法包括变量与数据类型：整数、浮点数、字符串、列表、元组、字典和集合。"
            "控制流通过 if/elif/else、for、while 实现，函数用 def 定义并支持默认参数与关键字参数。"
            "列表推导式 list comprehension 可以一行生成列表，例如 [x**2 for x in range(10)]。"
            "异常处理使用 try/except/finally，捕获特定异常类型以优雅处理错误。"
            "Python 的优雅之处在于可读性显著，是 AI 应用开发的首要语言。"
            "实战建议：先完成变量、循环、函数三个基础关卡的练习，再进入数据结构章节。"
        ),
    },
    {
        "title": "JavaScript/TypeScript 入门",
        "skill": "JavaScript/TypeScript",
        "source": "技能图谱配套课程",
        "content": (
            "JavaScript 是 Web 前端的事实标准语言，TypeScript 是其带类型系统的超集。"
            "核心概念包括变量声明 let/const、箭头函数、模板字符串、解构赋值。"
            "TypeScript 通过接口 interface 与类型注解在编译期发现错误，提升大型项目可维护性。"
            "DOM 操作通过 document.querySelector 与事件监听 addEventListener 完成。"
            "异步编程最重要的是 Promise 与 async/await，可避免回调地狱。"
            "前端框架 Vue/React 建立在组件化思想之上，数据驱动视图更新。"
            "练习题建议：实现一个 Todo 列表组件，练习状态管理与事件绑定。"
        ),
    },
    {
        "title": "机器学习基础概念",
        "skill": "机器学习基础",
        "source": "AI 理论课程",
        "content": (
            "机器学习是让计算机从数据中自动学习规律的一门学科。"
            "监督学习使用带标签数据训练模型，典型任务有分类与回归，常用算法包括线性回归、逻辑回归、决策树与随机森林。"
            "无监督学习在无标签数据中挖掘结构，典型有聚类（K-Means）与降维（PCA）。"
            "模型评估常用准确率、精确率、召回率与 F1 值，并划分训练集/验证集/测试集。"
            "过拟合指模型在训练集表现良好但泛化差，可用交叉验证、正则化与更多数据缓解。"
            "特征工程与数据清洗往往比模型选择更影响最终效果。"
            "机器学习与深度学习的关系：深度学习是机器学习的一个分支，基于多层神经网络。"
        ),
    },
    {
        "title": "提示工程与 LLM 应用",
        "skill": "提示工程",
        "source": "AI 理论课程",
        "content": (
            "提示工程（Prompt Engineering）是设计输入指令以引导大语言模型产生高质量输出的技术。"
            "核心原则：明确角色（system 设定）、给出上下文、拆分子任务、约束输出格式。"
            "Few-shot 通过提供少量示例帮助模型理解期望的输出模式，比零样本更稳定。"
            "结构化输出要求模型返回 JSON，便于程序解析与串联业务逻辑。"
            "温度参数控制随机性：低温度更确定，高温度更有创造性。"
            "常见的应用模式：摘要、问答（RAG 检索增强）、代码生成、角色扮演对话。"
            "RAG 技术将知识库检索结果注入提示，有效缓解模型幻觉并让答案带引用。"
        ),
    },
    {
        "title": "Web 全栈与 API 设计",
        "skill": "Web 全栈开发",
        "source": "工程实践课程",
        "content": (
            "Web 全栈开发涵盖前端界面、后端服务与数据库三个层次。"
            "RESTful API 设计遵循资源化与动词屏蔽：用 HTTP 方法表达操作，GET 读、POST 建、PUT 改、DELETE 删。"
            "后端框架 FastAPI 基于类型注解自动生成 OpenAPI 文档，异步支持良好。"
            "数据库设计关注范式与索引，事务保证数据一致性。"
            "前后端通过 JSON 交互，前端框架负责渲染与状态管理。"
            "部署环节包括反向代理、静态资源托管与进程守护（如 Nginx + uvicorn）。"
            "工程最佳实践：分层架构、环境变量配置、单元测试、日志与监控。"
            "练习建议：独立开发一个带增删改查的图书管理 API 并配套简单前端页面。"
        ),
    },
]


async def seed_chat_knowledge(db: Session) -> Dict[str, int]:
    """按文档标题幂等写入示例知识文档（异步：内部调用 index_document）。"""
    created = 0
    for item in _DOCS:
        exists = db.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.title == item["title"]
            )
        )
        if exists is not None:
            continue
        node = db.scalar(
            select(SkillNode).where(
                SkillNode.name == item["skill"], SkillNode.node_type == "skill"
            )
        )
        await index_document(
            db,
            title=item["title"],
            content=item["content"],
            source=item["source"],
            skill_node_id=node.id if node else None,
        )
        created += 1
    return {"documents": len(_DOCS), "created": created}