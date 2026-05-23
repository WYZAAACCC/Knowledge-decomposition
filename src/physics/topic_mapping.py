CN_TO_EN = {
    "广义相对论": "general_relativity", "狭义相对论": "special_relativity",
    "麦克斯韦方程组": "maxwell", "麦克斯韦方程": "maxwell",
    "薛定谔方程": "schrodinger", "狄拉克方程": "dirac",
    "纳维-斯托克斯方程": "navier_stokes", "纳维斯托克斯方程": "navier_stokes",
    "玻尔兹曼分布": "boltzmann_distribution", "热力学第二定律": "second_law_thermodynamics",
    "杨-米尔斯场论": "yang_mills", "杨米尔斯场论": "yang_mills",
    "洛伦兹变换": "lorentz_transform", "吉布斯自由能": "gibbs_free_energy",
    "配分函数": "partition_function", "哈密顿力学": "hamiltonian_mechanics",
    "拉格朗日力学": "lagrangian_mechanics", "傅里叶变换": "fourier_transform",
    "欧拉方程": "euler_equation", "连续性方程": "continuity_equation",
    "伯努利方程": "bernoulli", "牛顿第二定律": "newton_second",
    "爱因斯坦场方程": "einstein_field", "克莱因-戈尔登方程": "klein_gordon",
    "克莱因戈尔登方程": "klein_gordon", "费曼路径积分": "feynman_path_integral",
    "海森堡不确定性原理": "heisenberg_uncertainty", "泡利不相容原理": "pauli_exclusion",
    "卡诺定理": "carnot_theorem", "熵增原理": "entropy_increase",
    "涨落定理": "fluctuation_theorem", "朗之万方程": "langevin_equation",
    "福克-普朗克方程": "fokker_planck", "弗克普朗克方程": "fokker_planck",
    "波动方程": "wave_equation", "扩散方程": "diffusion_equation",
    "泊松方程": "poisson_equation", "拉普拉斯方程": "laplace_equation",
    "赫尔姆霍兹方程": "helmholtz_equation", "格林函数": "green_function",
    "规范场论": "gauge_field_theory", "量子场论": "quantum_field_theory",
    "统计力学": "statistical_mechanics", "量子电动力学": "qed",
    "量子色动力学": "qcd", "标准模型": "standard_model",
    "重整化群": "renormalization_group", "对称性破缺": "symmetry_breaking",
    "黑体辐射": "blackbody_radiation", "光电效应": "photoelectric_effect",
    "康普顿散射": "compton_scattering", "隧道效应": "tunneling_effect",
    "玻尔兹曼输运方程": "boltzmann_transport", "玻尔兹曼H定理": "boltzmann_h_theorem",
    "弹性力学张量": "elasticity_tensor", "克尔时空度规": "kerr_metric",
    "雷桥杜里方程": "raychaudhuri", "施温格-戴森方程": "schwinger_dyson",
    "马约拉纳方程": "majorana", "金兹堡-朗道方程": "ginzburg_landau",
    "刘维尔方程": "liouville", "弗拉索夫方程": "vlasov",
    "磁流体方程组": "mhd", "MHD方程": "mhd",
    "杨-米尔斯方程": "yang_mills", "杨米尔斯方程": "yang_mills",
    "N-S方程": "navier_stokes", "NS方程": "navier_stokes",
}

EN_TO_CN = {v: k for k, v in CN_TO_EN.items()}
EN_TO_CN.update({
    "navier_stokes": "纳维-斯托克斯方程",
    "maxwell": "麦克斯韦方程组",
    "yang_mills": "杨-米尔斯场论",
    "klein_gordon": "克莱因-戈尔登方程",
    "fokker_planck": "福克-普朗克方程",
    "mhd": "磁流体方程组",
    "boltzmann_distribution": "玻尔兹曼分布",
    "second_law_thermodynamics": "热力学第二定律",
    "feynman_path_integral": "费曼路径积分",
    "heisenberg_uncertainty": "海森堡不确定性原理",
    "pauli_exclusion": "泡利不相容原理",
    "carnot_theorem": "卡诺定理",
    "entropy_increase": "熵增原理",
    "fluctuation_theorem": "涨落定理",
    "langevin_equation": "朗之万方程",
    "fokker_planck": "福克-普朗克方程",
    "boltzmann_transport": "玻尔兹曼输运方程",
    "boltzmann_h_theorem": "玻尔兹曼H定理",
    "elasticity_tensor": "弹性力学张量",
    "kerr_metric": "克尔时空度规",
    "raychaudhuri": "雷桥杜里方程",
    "schwinger_dyson": "施温格-戴森方程",
    "majorana": "马约拉纳方程",
    "ginzburg_landau": "金兹堡-朗道方程",
    "liouville": "刘维尔方程",
    "vlasov": "弗拉索夫方程",
    "mhd": "磁流体方程组",
})

TOPIC_DEFINITIONS = {
    "partition_function": "统计力学配分函数Z=Σᵢe^(-βEᵢ)，是连接微观态与宏观热力学量的核心函数",
    "green_function": "物理学中的格林函数G(x,x')，是微分方程的积分核",
    "euler_equation": "流体力学中的欧拉方程，描述无粘性流体的运动方程",
    "lagrangian_mechanics": "分析力学的拉格朗日力学，基于拉格朗日量L=T-V和最小作用量原理",
    "hamiltonian_mechanics": "分析力学的哈密顿力学，基于哈密顿量H和正则方程",
    "continuity_equation": "连续性方程∂ρ/∂t+∇·(ρv)=0，描述物理量的守恒律",
    "diffusion_equation": "扩散方程∂c/∂t=D∇²c，描述物质浓度随时间的扩散过程",
    "entropy_increase": "熵增原理，孤立系统的熵永不减少",
    "fluctuation_theorem": "涨落定理，描述小尺度系统中熵产生涨落的对称性关系",
    "fokker_planck": "福克-普朗克方程，描述概率密度函数随时间演化的偏微分方程",
    "langevin_equation": "朗之万方程，描述布朗运动等随机过程的随机微分方程",
    "klein_gordon": "克莱因-戈尔登方程(□+m²)φ=0，相对论性标量场的波动方程",
    "yang_mills": "杨-米尔斯场论，基于非阿贝尔规范群的规范场理论",
    "renormalization_group": "重整化群，研究物理系统在不同尺度下行为变化的理论框架",
    "symmetry_breaking": "对称性破缺，系统从对称态转变为不对称态的物理过程",
    "second_law_thermodynamics": "热力学第二定律，孤立系统的熵永不减少ΔS≥0",
    "boltzmann_distribution": "玻尔兹曼分布P(E)∝e^(-βE)",
    "gibbs_free_energy": "吉布斯自由能G=H-TS，等温等压过程的自发性判据",
    "lorentz_transform": "洛伦兹变换，狭义相对论中惯性参考系之间的时空坐标变换",
    "dirac": "狄拉克方程(iγ^μ∂_μ-m)ψ=0，描述自旋1/2费米子的相对论性量子力学方程",
    "schrodinger": "薛定谔方程iℏ∂ψ/∂t=Ĥψ，量子力学中描述量子态随时间演化的基本方程",
    "maxwell": "麦克斯韦方程组，描述电磁场的基本方程组",
    "navier_stokes": "纳维-斯托克斯方程，描述粘性流体运动的基本方程",
    "general_relativity": "广义相对论，爱因斯坦的引力理论G_μν=8πGT_μν/c⁴",
    "newton_second": "牛顿第二定律F=ma",
    "bernoulli": "伯努利方程p+½ρv²+ρgh=常数",
    "einstein_field": "爱因斯坦场方程G_μν+Λg_μν=8πG/c⁴·T_μν",
    "special_relativity": "狭义相对论，基于光速不变原理和相对性原理的时空理论",
    "wave_equation": "波动方程∂²u/∂t²=c²∇²u",
    "poisson_equation": "泊松方程∇²φ=-ρ/ε₀",
    "laplace_equation": "拉普拉斯方程∇²φ=0",
    "helmholtz_equation": "赫尔姆霍兹方程(∇²+k²)φ=0",
    "fourier_transform": "傅里叶变换F(ω)=∫f(t)e^(-iωt)dt",
    "carnot_theorem": "卡诺定理，所有工作于同温热源之间的热机以可逆热机效率最高",
    "heisenberg_uncertainty": "海森堡不确定性原理ΔxΔp≥ℏ/2",
    "pauli_exclusion": "泡利不相容原理，费米子不能占据相同的量子态",
    "feynman_path_integral": "费曼路径积分，对所有可能路径的相位求和",
    "blackbody_radiation": "黑体辐射，普朗克公式描述的辐射谱",
    "photoelectric_effect": "光电效应，光子能量E=hν大于逸出功时电子从金属表面逸出",
    "compton_scattering": "康普顿散射，X射线被电子散射后波长增大的现象",
    "tunneling_effect": "量子隧穿效应，粒子穿越经典力学禁止区域的量子现象",
    "standard_model": "粒子物理标准模型SU(3)×SU(2)×U(1)规范理论",
    "qed": "量子电动力学QED",
    "qcd": "量子色动力学QCD",
    "gauge_field_theory": "规范场论，基于局部对称性的场论框架",
    "quantum_field_theory": "量子场论，将量子力学和狭义相对论结合的理论框架",
    "statistical_mechanics": "统计力学，从微观粒子运动推导宏观热力学性质的桥梁理论",
    "boltzmann_transport": "玻尔兹曼输运方程",
    "boltzmann_h_theorem": "玻尔兹曼H定理dH/dt≤0",
    "elasticity_tensor": "弹性力学四阶张量C_ijkl",
    "kerr_metric": "克尔时空度规，描述旋转黑洞",
    "raychaudhuri": "雷桥杜里方程，描述测地线汇的聚焦行为",
    "schwinger_dyson": "施温格-戴森方程，量子场论中格林函数的自洽方程",
    "majorana": "马约拉纳方程，粒子为其自身反粒子",
    "ginzburg_landau": "金兹堡-朗道方程，描述超导体的宏观量子行为",
    "liouville": "刘维尔方程∂ρ/∂t={H,ρ}",
    "vlasov": "弗拉索夫方程，描述等离子体中粒子分布的无碰撞演化",
    "mhd": "磁流体方程组",
}


_MODERN_PHYSICS_CN = {"相对论", "洛伦兹", "爱因斯坦", "量子", "狄拉克", "薛定谔",
                       "杨-米尔斯", "杨米尔斯", "场论", "克莱因", "戈尔登",
                       "费米", "马约拉纳", "施温格", "戴森", "金兹堡", "朗道",
                       "重整化", "规范", "色动力", "电动力", "标准模型",
                       "克尔", "度规", "雷桥杜里", "黑洞", "测地线"}
_MODERN_PHYSICS_EN = {"relativ", "lorentz", "einstein", "quantum", "dirac", "schrodinger",
                       "yang_mills", "gauge", "qed", "qcd", "klein_gordon", "pauli",
                       "heisenberg", "feynman", "standard_model", "majorana",
                       "schwinger_dyson", "renormalization", "ginzburg_landau",
                       "kerr_metric", "raychaudhuri", "symmetry_breaking",
                       "blackbody", "photoelectric", "compton", "tunneling"}
_ELECTROMAGNETISM_CN = {"电磁", "麦克斯韦", "电场", "磁场", "格林函数", "泊松", "拉普拉斯"}
_ELECTROMAGNETISM_EN = {"maxwell", "electro", "magnet", "poisson", "laplace", "green_function",
                         "helmholtz"}
_THERMODYNAMICS_CN = {"热力学", "熵", "玻尔兹曼", "吉布斯", "配分", "卡诺", "涨落",
                       "福克", "普朗克", "朗之万", "刘维尔", "输运"}
_THERMODYNAMICS_EN = {"thermo", "entropy", "boltzmann", "gibbs", "partition",
                       "carnot", "fluctuation", "statistic", "fokker_planck",
                       "langevin", "liouville", "boltzmann_transport", "boltzmann_h"}
_SOLID_MECHANICS_CN = {"弹性", "张量", "固体"}
_SOLID_MECHANICS_EN = {"elasticity", "tensor", "solid_mechanics"}


def infer_node_type(text: str) -> str:
    if any(k in text for k in ["方程", "等式", "度规", "变换"]):
        return "equation"
    if any(k in text for k in ["定律", "定理", "原理"]):
        return "law"
    if any(k in text for k in ["函数", "系数", "常数", "能量", "熵"]):
        return "quantity"
    t = text.lower()
    if any(k in t for k in ["equation", "transform", "metric"]):
        return "equation"
    if any(k in t for k in ["law", "theorem", "principle"]):
        return "law"
    if any(k in t for k in ["function", "coefficient", "constant", "energy"]):
        return "quantity"
    return "concept"


def infer_domain(text: str) -> str:
    if any(k in text for k in _MODERN_PHYSICS_CN):
        return "modern_physics"
    t = text.lower()
    if any(k in t for k in _MODERN_PHYSICS_EN):
        return "modern_physics"
    if any(k in text for k in _ELECTROMAGNETISM_CN):
        return "electromagnetism"
    t = text.lower()
    if any(k in t for k in _ELECTROMAGNETISM_EN):
        return "electromagnetism"
    if any(k in text for k in _THERMODYNAMICS_CN):
        return "thermodynamics"
    t = text.lower()
    if any(k in t for k in _THERMODYNAMICS_EN):
        return "thermodynamics"
    if any(k in text for k in _SOLID_MECHANICS_CN):
        return "mechanics"
    t = text.lower()
    if any(k in t for k in _SOLID_MECHANICS_EN):
        return "mechanics"
    return "mechanics"


def infer_domain_hint(target: str) -> str:
    t = target.lower()
    if any(k in t for k in ["relativ", "lorentz", "einstein",
                              "kerr", "raychaudhuri", "schwarzschild"]):
        return "相对论物理学"
    if any(k in t for k in ["quantum", "schrodinger", "dirac", "klein_gordon", "pauli",
                             "heisenberg", "feynman", "yang_mills", "gauge", "qed", "qcd",
                             "standard_model", "schwinger_dyson", "renormalization",
                             "majorana", "ginzburg_landau", "symmetry_breaking"]):
        return "量子物理学"
    if any(k in t for k in ["maxwell", "electro", "magnet", "poisson", "laplace", "green_function",
                             "helmholtz"]):
        return "电磁学"
    if any(k in t for k in ["liouville", "vlasov", "boltzmann_transport", "boltzmann_h",
                             "fokker_planck", "langevin"]):
        return "统计力学与非平衡态物理"
    if any(k in t for k in ["thermo", "entropy", "boltzmann", "gibbs", "partition",
                             "carnot", "fluctuation", "statistic"]):
        return "热力学与统计力学"
    if any(k in t for k in ["navier", "stokes", "fluid", "euler", "bernoulli",
                             "continuity", "diffusion", "mhd"]):
        return "流体力学"
    if any(k in t for k in ["elasticity", "tensor", "solid_mechanics"]):
        return "固体力学"
    if any(k in t for k in ["hamilton", "lagrangian", "newton", "wave_equation"]):
        return "经典力学"
    return "物理学"


def infer_theory_context(target: str, domain) -> str:
    from ..models import TheoryContext
    t = target.lower()
    d = str(domain.value if hasattr(domain, 'value') else domain).lower()
    if "relativ" in d or any(k in t for k in ["relativ", "lorentz", "einstein",
                                                "einstein_field", "kerr_metric",
                                                "raychaudhuri", "schwarzschild"]):
        return TheoryContext.RELATIVISTIC
    if "quantum" in d or any(k in t for k in ["schrodinger", "dirac", "klein_gordon",
                                                "pauli", "heisenberg", "feynman",
                                                "yang_mills", "gauge", "qed", "qcd",
                                                "standard_model", "majorana",
                                                "schwinger_dyson", "renormalization",
                                                "symmetry_breaking", "ginzburg_landau"]):
        return TheoryContext.QUANTUM_INTRO
    if "statistic" in d or "thermo" in d or any(k in t for k in ["boltzmann", "partition", "gibbs",
                                                  "carnot", "fluctuation", "entropy",
                                                  "fokker_planck", "langevin", "liouville",
                                                  "boltzmann_transport", "boltzmann_h",
                                                  "vlasov"]):
        return TheoryContext.STATISTICAL
    return TheoryContext.CLASSICAL


def get_cn_topic_name(target: str) -> str:
    target_lower = target.lower()
    for en, cn in EN_TO_CN.items():
        if en in target_lower:
            return cn
    parts = target.split('.')
    if len(parts) > 1:
        return parts[-1].replace('_', ' ')
    return target


def get_topic_definition(target: str) -> str:
    target_lower = target.lower()
    for key, definition in TOPIC_DEFINITIONS.items():
        if key in target_lower:
            return definition
    return f"{target}是物理学中的一个重要概念"


class TopicMapping:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.cn_to_en = CN_TO_EN
            cls._instance.en_to_cn = EN_TO_CN
        return cls._instance

    def cn_to_en_lookup(self, text: str) -> str:
        return self.cn_to_en.get(text, "")

    def en_to_cn_lookup(self, en_name: str) -> str:
        return self.en_to_cn.get(en_name, "")
