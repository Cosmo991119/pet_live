# Meshy AI 岗位面试准备

更新时间：2026-05-06

目标不是把自己包装成“大模型训练工程师”，而是结合已有经历，定位成：

> 有 C++、2D 计算几何、3D 打印切片路径经验，正在向 AI 3D 工具 / 图形管线 / 多模态产品工程转型的工程师。

相关岗位链接：

- [Generative AI - Graphics Engineer](https://jobs.ashbyhq.com/meshy/1806f5d3-9f34-4e7e-8238-4e53fc4e579b)
- [AI Product Engineer (3D Full Stack)](https://jobs.ashbyhq.com/meshy/eadb780d-e44a-4063-a0ff-5c42fd27b9af)
- [Meshy Careers](https://www.meshy.ai/zh/careers)

## 个人背景定位

已有优势：

- C++ 工程经验
- 3D 打印行业经验
- 2D 计算几何经验
- 切片路径相关算法经验
- 轮廓、偏置、填充、布尔、路径规划等经验
- 对 3D 模型、图像处理、游戏、宠物、AI Agent 感兴趣

需要诚实表达的边界：

- 不是大模型训练背景
- 不是纯 3D 网格 / 渲染引擎专家
- 不是成熟前端全栈工程师
- Python、AI Agent、WebGL / Three.js / React 仍在补

推荐表达：

> 我过去主要做 C++ 和 3D 打印切片中的 2D 计算几何，比如轮廓处理、偏置、填充、布尔、路径规划等。现在希望把这部分几何算法和工程落地能力，迁移到 AI 3D 生成后的资产质量检查、几何处理、工具链和产品化流程里。

## 岗位一：Generative AI - Graphics Engineer

### 岗位本质

这个岗位不是普通 AI 应用岗，也不是单纯训练大模型。它更像：

> 中高级图形 / 几何 / 图形系统工程师，服务于 AI 3D 生成训练与产品管线。

核心关键词：

- Modern C++
- GPU programming
- Computer graphics
- Rendering
- Geometry processing
- Simulation
- Production-quality graphics systems
- Geometry pipeline
- Asset tools
- DCC tools: Blender / Houdini / Maya

### 匹配度判断

当前可以投，但不是高概率岗位。

匹配点：

- C++ 背景
- 2D 计算几何
- 3D 打印切片经验
- 轮廓、偏置、填充、布尔、路径规划经验
- 几何算法工程化经验
- 对 3D 资产可用性和打印流程有理解

短板：

- GPU / CUDA / OpenGL / Vulkan 经验可能不足
- 3D 网格处理经验可能不足
- 渲染引擎、游戏/VFX/DCC 管线经验可能不足
- 不是纯 AI 3D foundation model 训练背景

结论：

> 可以作为冲刺岗位投。简历和面试不要主打“大模型”，要主打 C++、几何处理、图形算法、生产级几何管线和切片路径经验。

### 是否要求大模型

不把大模型训练作为核心硬要求。岗位名字有 Generative AI，但核心是为 AI 3D 生成产品做图形系统、几何处理、渲染 / 资产管线。

需要理解：

- text-to-3D / image-to-3D 是什么
- AI 生成 3D 资产常见问题
- 为什么生成模型需要后处理
- 资产如何进入游戏、打印、设计、动画流程

可以这样答：

> 我目前不把自己定位成模型训练工程师，而是图形 / 几何管线工程师。我更关注 AI 生成 3D 资产之后，如何通过几何处理、质量检查、格式转换和可用性验证，让它成为 production-ready asset。

### 面试问题准备

#### C++ 与工程能力

准备点：

- `vector`、`map`、`unordered_map`、`set` 的使用场景
- 智能指针：`unique_ptr`、`shared_ptr`、循环引用
- 对象生命周期、拷贝 / 移动语义
- 多线程、锁、竞态、任务并行
- 性能优化、profiling、减少拷贝、缓存友好
- 浮点误差、`epsilon`、几何容差

可能问题：

- 你在切片算法里遇到过哪些性能瓶颈？怎么优化？
- C++ 里什么时候用引用，什么时候用指针？
- 你怎么避免几何算法里的浮点误差？
- 如果一个大网格文件导致内存爆了，你会怎么处理？

#### 计算几何 / 图形算法

准备点：

- 点、线段、多边形基础操作
- 点在多边形内判断
- 线段相交
- 多边形面积、方向、外轮廓 / 内洞
- 多边形 offset / inflate / inset
- 布尔运算基本思路
- 扫描线算法
- 空间索引：AABB、grid、KD-tree、BVH
- 路径规划：轮廓路径、填充路径、路径排序

可能问题：

- 多边形偏置为什么容易出错？
- 自相交多边形怎么处理？
- 点在多边形内有哪些算法？
- 如何判断两个三角形 / 两条线段是否相交？
- 切片路径生成有哪些难点？
- 如果 AI 生成的模型有破面、非流形、自相交，你怎么检测？

#### 3D 图形基础

准备点：

- mesh：vertex / edge / face / normal / UV
- manifold / non-manifold
- watertight mesh
- normal 计算与翻转
- bounding box
- ray casting
- SDF：Signed Distance Field
- marching cubes
- remesh / decimation / subdivision
- OBJ / STL / GLB / FBX 区别
- PBR 材质：base color、roughness、metallic、normal map

可能问题：

- STL 和 OBJ 有什么区别？
- 什么是 non-manifold mesh？
- 怎么判断一个 mesh 是否 watertight？
- 法线错误会造成什么问题？
- SDF 在 3D 生成 / 几何处理中有什么用？
- AI 生成的 3D 模型要进入游戏或打印流程，需要哪些后处理？

#### GPU / 渲染基础

准备点：

- CPU vs GPU 并行差异
- OpenGL / Vulkan / CUDA / WebGL 分别做什么
- vertex shader / fragment shader
- rasterization 基本流程
- draw call
- texture / framebuffer
- GPU 加速适合什么任务

可能问题：

- GPU 为什么适合图形计算？
- 渲染一个三角形大概经过哪些流程？
- OpenGL 和 CUDA 的区别？
- 什么任务适合放 GPU，什么不适合？

推荐回答边界：

> 我之前主要是 C++ CPU 侧几何算法和切片路径，GPU / 渲染不是主线，但我在补 OpenGL / WebGL 基础，希望把几何处理能力扩展到 AI 3D 资产管线。

### 推荐 Demo：AI 3D Asset Geometry Inspector / Slicing Preview Tool

目标：

> 输入一个 `.stl` 或 `.obj` 模型，输出模型基本信息、几何质量检查、简单切片预览、2D 轮廓 / 路径可视化，以及可打印性 / 可用性建议报告。

技术栈：

- C++：核心几何处理
- Clipper2：多边形 offset / boolean
- Python：可视化 / 脚本胶水，可选
- Open3D / trimesh：读取和检查模型，可选
- Blender Python：导入导出 / 截图，可选
- Three.js：后续做网页 3D 预览，可选

MVP 功能，2-3 周：

- 读取 `.stl`
- 输出顶点数、三角面数、包围盒尺寸
- 检查重复点、退化三角形
- 检查 boundary edge 和 non-manifold edge
- 对指定高度做单层切片
- 求三角面和平面的交线
- 输出 2D 线段集合
- 生成 SVG / PNG 切片预览

进阶功能，4-6 周：

- 多层切片预览
- 轮廓连接成 polyline / polygon
- 多边形 offset：外墙、内墙
- 简单 infill：直线填充、网格填充
- 路径排序，减少空走
- 输出 JSON / Markdown 几何报告

冲刺功能，6-8 周：

- 支持 OBJ / GLB
- Three.js 网页预览
- 模型问题高亮：非流形边、破洞区域
- 简单修复：删除退化面、合并近距离点、法线统一
- 接入 LLM API，自动解释几何报告
- README、架构图、demo 视频、性能对比

### 8 周准备计划

第 1 周：3D mesh 基础

- 搞懂 STL / OBJ
- 搞懂 vertex / face / edge / normal
- 写 STL parser 或用库读取 STL
- 输出模型基本信息

第 2 周：mesh 质量检查

- edge map
- non-manifold 检测
- boundary edge 检测
- duplicated vertex 检测

第 3 周：单层切片

- 三角形和平面求交
- 得到 2D 线段
- 输出 SVG

第 4 周：轮廓连接与可视化

- 把线段连接成 polyline
- 处理容差
- 区分闭合 / 未闭合轮廓
- 生成更清晰的切片预览图

第 5 周：offset / infill

- 接入 Clipper2
- 做轮廓 offset
- 生成简单直线填充

第 6 周：路径优化与性能

- 简单路径排序
- 统计路径长度、空走距离
- 做 profiling
- 优化数据结构

第 7 周：AI 3D 资产报告

- 把检查结果组织成报告
- 可选接入 LLM API
- 输出 Markdown 报告

第 8 周：作品集整理

- README 写清楚
- 录 1-2 分钟 demo 视频
- 准备面试讲稿
- 简历加项目经历

简历写法：

> Built a C++ geometry inspection and slicing preview tool for 3D assets. Implemented STL mesh parsing, non-manifold/boundary edge detection, plane-mesh slicing, 2D contour reconstruction, polygon offset, infill generation, and path optimization. Generated visual reports for asset quality and printability analysis.

## 岗位二：AI Product Engineer (3D Full Stack)

### 岗位本质

这个岗位更像：

> 面向 AI 3D 创作工具的图形前端 / 产品工程师。

它不是普通后端，也不是大模型训练岗。它主要负责把 AI 3D 能力做成用户能直接使用的 Web 工具和创作流程。

核心关键词：

- TypeScript
- React
- WebGL
- Three.js / R3F
- web-based 3D editor
- 3D creative workflows
- model / texture editing
- character animation systems
- procedural asset generation pipelines
- interactive 3D experience
- UX / product interaction

### 匹配度判断

当前匹配度低于 Graphics Engineer，但长期转型价值很高。

匹配点：

- 懂 3D 打印和几何问题
- 有 C++ 算法工程经验
- 对 3D 模型、图像处理、AI Agent、创作工具感兴趣
- 能理解 3D 工具用户遇到的真实问题
- 如果补 WebGL / Three.js，可以形成“懂几何的 3D 产品工程师”差异化

短板：

- 当前可能缺 TypeScript / React 商业项目经验
- 当前可能缺 WebGL / Three.js / R3F 经验
- 当前可能缺 web-based editor 或 creative tool 作品
- 当前不是成熟 full stack / frontend engineer
- Python 和 AI agent 还在入门阶段

结论：

> 现在不建议作为主投最高优先级，除非短期能做出 Three.js / React 3D 工具 demo。它更适合作为 3-6 个月转型目标。

### 是否要求大模型

不要求你训练大模型，但需要理解生成式 AI 如何进入产品。

重点不是：

- 训练 diffusion / transformer
- 写底层模型结构
- 做大规模训练

重点是：

- 调用 AI 生成能力
- 设计 3D 创作工作流
- 让生成、编辑、预览、导出变成顺滑产品体验
- 把 AI 输出的模型 / 贴图 / 动画放进 Web 3D 编辑器

推荐表达：

> 我更关注 AI 3D 能力的产品化和工具化：用户上传图片或输入提示词后，系统如何生成模型、预览模型、编辑材质、检查几何质量，并导出到游戏、打印或设计流程。

### 面试问题准备

#### TypeScript / React / 前端基础

准备点：

- TypeScript 类型系统：interface、type、generic、union
- React hooks：`useState`、`useEffect`、`useMemo`、`useCallback`
- 组件拆分和状态管理
- 异步请求和错误处理
- 性能优化：memo、虚拟列表、避免重复渲染
- 前端工程化：Vite、ESLint、构建、部署

可能问题：

- React 组件为什么会重复渲染？怎么优化？
- `useEffect` 依赖数组怎么理解？
- TypeScript 中 interface 和 type 的区别？
- 你怎么设计一个 3D 文件上传和任务状态轮询组件？
- 一个生成任务需要 30 秒，前端怎么展示进度和失败状态？

#### WebGL / Three.js / R3F

准备点：

- scene / camera / renderer
- mesh / geometry / material
- light / shadow
- texture / normal map
- OrbitControls
- GLTFLoader / OBJLoader / STLLoader
- raycaster：点击选择模型
- bounding box / fit camera
- animation loop
- dispose geometry / material，避免内存泄漏

可能问题：

- Three.js 渲染一个模型需要哪些对象？
- 怎么加载 GLB / OBJ / STL？
- 怎么让相机自动对准模型？
- 怎么实现点击选中模型的一部分？
- WebGL 场景卡顿，你怎么排查？
- geometry / material / texture 为什么要 dispose？

#### 3D 编辑器 / 创作工具设计

准备点：

- 文件上传
- 模型预览
- 模型选择 / 变换 / 缩放 / 旋转
- 材质编辑
- 贴图替换
- 历史记录：undo / redo
- 导出格式
- 任务队列和生成状态
- 用户体验：loading、错误、空状态、失败重试

可能问题：

- 如果让你设计一个 web-based 3D editor，你会怎么拆模块？
- 怎么实现模型编辑历史记录？
- 生成式 AI 的结果不稳定，产品上怎么处理？
- 用户上传很大的模型，前端怎么保证不卡？
- 模型预览和模型编辑的状态怎么管理？

#### AI Product / Workflow 理解

准备点：

- text-to-3D / image-to-3D 用户流程
- prompt、生成参数、任务队列
- 生成结果版本管理
- 生成失败重试
- 模型质量反馈
- 用户可控编辑
- 导出到 Blender / Unity / Unreal / 3D 打印

可能问题：

- 你会如何设计 image-to-3D 的用户流程？
- AI 生成结果不好，怎么让用户继续编辑？
- 如何把几何质量检查融入产品体验？
- 如果用户想把模型用于 3D 打印，你会给哪些提示？
- 如果用户想把模型用于游戏，你会关注哪些指标？

### 推荐 Demo：AI 3D Web Product Editor

目标：

> 做一个 Web 版 AI 3D 资产查看、编辑、检查和报告工具，证明自己具备 AI Product Engineer 所需的 TypeScript / React / Three.js / 产品工程能力。

建议技术栈：

- TypeScript
- React
- Vite
- Three.js 或 React Three Fiber
- Zustand 或 React state
- Tailwind 或普通 CSS
- 可选：FastAPI / Node.js mock server
- 可选：OpenAI API / 其他 LLM API

MVP 功能，2-3 周：

- 上传 `.glb` / `.obj` / `.stl`
- 3D 模型预览
- OrbitControls 查看模型
- 显示模型信息：文件名、格式、大小、包围盒
- 自动 fit camera
- 基础材质切换：matcap / normal / wireframe
- 错误状态、loading 状态、空状态

进阶功能，4-6 周：

- 模型列表和版本记录
- 点击选中模型
- transform controls：移动、旋转、缩放
- 材质编辑：颜色、roughness、metalness
- 截图导出
- 模拟 AI 生成任务：pending / running / success / failed
- 生成结果对比：before / after

冲刺功能，6-8 周：

- 接入后端几何检查结果
- 展示 non-manifold / boundary / thin wall 等报告
- 问题区域高亮，可先用 mock data
- 接入 LLM API，生成可读建议
- Prompt 面板：输入“生成一个低多边形游戏道具”等
- 结果版本管理
- 导出 report
- README、架构图、demo 视频

### 8 周准备计划

第 1 周：TypeScript + React 基础

- Vite 创建项目
- 组件拆分
- 文件上传组件
- 状态管理
- loading / error / empty 状态

第 2 周：Three.js 基础

- scene / camera / renderer
- OrbitControls
- 加载 GLB / OBJ / STL
- fit camera
- wireframe / normal / basic material

第 3 周：做 3D Viewer MVP

- 上传模型
- 预览模型
- 显示基本信息
- 支持重置视角
- 支持截图

第 4 周：编辑器交互

- 选中模型
- transform controls
- 材质颜色修改
- 侧边属性面板
- 响应式布局

第 5 周：AI 生成任务流

- prompt 输入框
- mock 生成任务
- 任务状态轮询
- 生成结果版本列表
- before / after 对比

第 6 周：接几何检查报告

- 引入 Graphics Demo 或 mock report
- 展示顶点数、面数、包围盒、non-manifold 数量
- 问题严重程度标记
- 生成 Markdown / JSON 报告

第 7 周：LLM 解释和产品化

- 接入 LLM API，可选
- 根据几何报告生成建议
- 针对游戏 / 打印 / 设计三种用途给不同建议
- 完善错误和重试

第 8 周：作品集整理

- README
- 架构图
- demo 视频
- 部署到 Vercel / Netlify，或本地录屏
- 简历项目描述

简历写法：

> Built a React + TypeScript web-based 3D asset editor prototype using Three.js. Implemented model upload, GLB/OBJ/STL preview, camera fitting, material controls, transform interactions, AI generation task states, geometry quality report display, and LLM-generated asset improvement suggestions.

### 和 Graphics Demo 的关系

最理想的作品集组合是两个 demo 串起来：

1. C++ Geometry Inspector：负责检查模型和生成几何报告
2. React + Three.js Web Editor：负责展示模型、交互编辑和解释报告

这样你可以同时覆盖两个岗位：

- 面 Graphics Engineer：重点讲 C++、几何、切片、质量检查
- 面 AI Product Engineer：重点讲 TypeScript、React、Three.js、用户工作流、AI 生成任务体验

## 两个岗位怎么选择

当前更适合优先投：

1. Generative AI - Graphics Engineer
2. AI 3D Dataset Engineer
3. Senior Geometry Processing Engineer，视 JD 细节而定
4. AI Product Engineer (3D Full Stack)，作为补完 Web 3D 作品后的目标

如果短期目标是提高命中率：

- 主攻 Graphics Engineer 相关准备
- 做 C++ Geometry Inspector / Slicing Preview Tool
- 简历突出 C++、计算几何、切片路径和工程优化

如果中期目标是转 AI Agent / AI 产品：

- 补 TypeScript / React / Three.js
- 做 AI 3D Web Product Editor
- 把 C++ 几何检查能力接到 Web 产品里

一句话策略：

> 先用 C++ + 几何经验拿到 AI 3D 公司的面试入口，再逐步补 Web 3D 和 AI Product 能力，转成“懂几何的 AI 3D 工具工程师”。
