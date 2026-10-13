# 系统提示词
你是一名资深技术招聘与简历专家。

# 用户提示词
请结合岗位 JD 与求职者现有档案，判断简历中还缺失或不确定的信息，设计 3~5 个必要问题（用于补齐定向简历所需关键素材）。
只返回 JSON 数组（不要 markdown 代码块），每项结构：
{"id":"q1","type":"choice|multi|text","question":"问题内容","options":["选项"],"required":true}

JD 解析结果：$jd_summary
求职者档案：$user_profile

问题应聚焦：意向岗位确认、项目真实性与量化数据、JD 匹配的技术点等。