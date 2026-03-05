# project code reinforced learning

## basic environment

> project root directory

1. `/main.py`

- 属于脚手架占位文件, 不包含业务逻辑
- 可做 _冒烟测试_ , 运行 `uv run main.py` , 返回欢迎信息

2. `pyproject.toml`

- 项目配置文件, 包括 项目元数据、依赖、工具配置 等.
- '[project]' : 基本元信息 和 依赖项(dependencies)
- '[project.optional-dependencies]' - 可选依赖项(开发用)
- '[toll.ruff]': Ruff 代码风格检查
- '[tool.pytest.ini_options]': pytest 设置

3. `pyrightconfig.json`

- Pyright 语言服务器的配置文件(另外可选Pylance), 用于控制哪些文件参与类型检查,如何处理虚拟环境以及设定检查级别.
- `include` : 需要分析的路径和文件
- `exclude` : 忽略的路径模式(缓存目录、虚拟环境、归档文件等), 避免浪费资源
- `venvPath/venv` : 指定虚拟环境位置, 让 Pyright 解析依赖包的类型信息
- `typeCheckMode` : 设定检查级别, 建议 'basic'
- `reportMissingTypeStubs` : 'none' 表示库中缺少类型存根的时候不报错,避免对第三方包产生大量的报错信息
- `useLibraryCodeForTypes` : 允许从已安装库的源代码推断类型

4. `.env.example & .env`

- 配置文件,首次拉起开发服务环境,需要拷贝example文件,生成`.env`文件

## backend

> `src/apps/api/`

1. `main.py`

- _应用启动脚本_ , 模块和段落的排序遵循思路是: 先准备环境 -> 再创建`app`实例 -> 然后装配功能(异常、限流、中间件) -> 最后挂载业务路由
- 导入与常量声明
  - 所有第三方和本地依赖先导入
  - `liminter/handler` 引入要早于使用
- 辅助函数: 定义局部作用的异常处理器,便于`app.add_exception_handler` 使用; 放在应用创建前是为了清晰,因为其不依赖`app`变量
- 基础设施初始化:
  - 日志最先启动, 以便补货整个启动流程中的任何问题
  - 紧接着创建`FastAPI`实例,所有后续都围绕`app`变量进行
- 全局状态与异常处理配置:
  - 将限流器挂载到`app.state`, 让其在请求上下文中可用
  - 注册应用异常处理器, 先于中间件和路由, 确保捕获所有错误
- 中间件注册: (顺序很重要)
  - 请求日志中间件
  - 认证上下文中间件
  - Trace ID 中间件
  - CORS 配置: 属于框架提供的标准中间件,位置重要性低,只要在路由前即可
    tips: 后添加的先执行: `TraceId`最外层包裹,`AutoContext`需要先有`TraceID`, `RequestLogging` 最内层记录最终状态
- 日志记录初始化成功: 通常在中间件装配完成之后
- 基础路由
  - 健康检查端点
  - 根路径
- 业务路由注册: 使用局部导入,避免循环引用,所有外围配置就绪后再引入并包含具体业务子路由,让他们在统一环境下运行
