# Verilog RTL 设计方法学 — 完整参考

## Phase 0: 硬件思维方法论

### 0.1 从晶体管到模块：逐层抽象

数字 IC 设计的正确思维路径：**晶体管 → 门电路 → 功能单元 → 模块 → 系统**。每一层都是上一层的基本元件组合。

```
晶体管级：NMOS/PMOS 开关、充放电、驱动能力
  ↓
门电路级：与/或/非/异或门、NAND/NOR、传输门、三态门
  ↓
功能单元级：触发器 FF、锁存器 Latch、MUX、加法器、乘法器、移位器、译码器
  ↓
模块级：状态机 FSM、流水线、FIFO、仲裁器、CRC、编码器
  ↓
系统级：总线互联、时钟树、复位网络、功耗域、DFT 扫描链
```

### 0.2 硬件与软件的根本差异

| 维度 | 硬件电路 | 软件程序 |
|------|---------|---------|
| 执行方式 | 所有逻辑**同时并行**工作 | 指令**逐条串行**执行 |
| 时间单位 | 时钟周期 CLK、建立/保持时间 | CPU 指令周期 |
| 存储 | 寄存器、SRAM、DRAM、ROM、锁存器 | 变量、数组、堆/栈 |
| 控制流 | 状态机 FSM、流水线握手 | 函数调用、循环、分支 |
| 数据 | bit 位宽、总线、码制 | 字节、类型、对象 |
| 正确性 | 时序收敛、亚稳态、毛刺 | 逻辑正确、内存安全 |
| 优化目标 | Fmax、面积、功耗、延迟 | 时间复杂度、空间复杂度 |

### 0.3 硬件设计四维权衡

任何设计决策都是四个维度的折中：

- **速度（Fmax）**：最高工作频率。加法器链延迟 > 流水级延迟 → 插寄存器拆分
- **面积（Area）**：门数、FF 数、RAM 块数。并行阵列面积大，时分复用面积小
- **功耗（Power）**：动态功耗（∝ 翻转率 × 电容 × V² × f）+ 静态功耗（漏电流）
- **延迟（Latency）**：输入到输出的时钟周期数。流水线加延迟但提吞吐

**不可能三角**：速度、面积、功耗不可兼得。任意两个优化必然牺牲第三个。

### 0.4 从软件思维到硬件思维的转换表

| 软件概念 | 硬件对应 |
|---------|---------|
| `for`/`while` 循环 | 状态机多周期迭代 / 流水线展开 / 并行硬件阵列 |
| `if`/`else` 条件 | 多路选择器 MUX、组合逻辑门 |
| `int x = 5;` 变量 | 寄存器 `reg [31:0] x_q` |
| 数组 `a[100]` | 寄存器堆 / SRAM / 多路选择器阵列 |
| 函数调用 | 模块实例化、组合逻辑块 |
| 递归 | 硬件不支持。拆为迭代状态机 |
| `malloc`/`free` | 硬件无动态分配。资源在综合时确定 |
| `sleep(ms)` | 计数器 + 使能信号。禁用绝对延时 `#delay` |
| 线程/并发 | 并行硬件模块、多时钟域 |
| try/catch 异常 | 溢出标志位、valid 信号、FIFO 满/空 |
| 内存地址/指针 | 总线地址译码、片选 CS 信号 |

---

## Phase 1: 规格与架构

### 1.1 先定义接口契约

在编写任何 RTL 代码之前，必须明确：

- **接口**：所有端口的信号方向、位宽和行为
- **模式/功能**：枚举所有操作模式
- **时序**：流水线深度、延迟、吞吐量要求
- **特殊情况**：零、无穷大、溢出、下溢、复位行为
- **数据格式**：位域定义（如 IEEE 754 FP16：符号[15] + 指数[14:10] + 尾数[9:0]）

> **⚠️ 接口规格必须在第一步锁定**：reset 极性（active-high/active-low）、握手协议（valid/ready/ack）、数据有效周期宽度必须在架构阶段以文档形式固定。多人/多模块协作时，接口不一致是集成阶段最难排查的问题之一。

### 1.2 流水线架构模板

```
状态机：IDLE → S0 → S1 → ... → SN → IDLE

每级结构：
  - 组合逻辑块：计算下一级所需的值（纯组合电路，无状态）
  - 时序寄存器块：在状态匹配时打拍寄存（D 触发器组）

Valid/Ready 握手：
  - i_enable & (state == IDLE) → 启动流水线
  - o_idle = (state == IDLE) → 反压上游、准备接收下一笔
```

### 1.3 一切皆参数化

```verilog
module my_module #(
    parameter DATA_WIDTH   = 16,
    parameter NUM_ELEMENTS = 16,
    parameter PROD_WIDTH   = 2 * DATA_WIDTH
) ( ... );
    localparam ACCUM_WIDTH = PROD_WIDTH + 4;
```

绝不硬编码位宽。`parameter` 声明可配置常量，`localparam` 声明派生常量。

### 1.4 硬件资源复用方法论

多模式设计（如混合精度计算引擎、多标准编解码器、多协议接口）中，不同工作模式下的并行度与数据位宽常呈**反比关系**。若按"最大并行度 × 最大位宽"声明所有寄存器和运算器，低精度模式下大量高位 bit 闲置，造成面积浪费。

#### 核心思想

**以物理资源上限为约束，通过模式感知的打包/解包逻辑，在不同模式间动态复用同一组物理资源。**

具体步骤：

1. **需求矩阵分析**：枚举所有模式下的并行度 × 位宽需求，识别各子系统的峰值需求与闲置区间
2. **物理资源定上限**：寄存器位宽/运算器数量按各模式的**合理交集**定义，而非最大值的简单笛卡尔积
3. **打包/解包桥接**：模块间传输紧凑格式节省寄存器，模块内展开全格式便于逐通道处理
4. **参数化配置**：通过 `parameter/localparam` 定义物理槽位数、位宽、并行度，支持跨配置裁剪

**案例：混合精度计算引擎（FP16/FP8/NVFP4）**

| 模式 | 并行度 | 尾数位宽 | 总尾数位宽需求 |
|------|--------|----------|---------------|
| FP16×FP16 | 16 | 11-bit | 16 × 11 = 176 bit |
| FP8×FP8 | 32 | 4-bit | 32 × 4 = 128 bit |
| NVFP4×FP8 | 32 | A:2-bit, B:4-bit | 32 × (2+4) = 192 bit |

若按最大并行度 × 最大位宽（32 × 11 = 352 bit）声明寄存器，FP8 模式下仅使用 128/352 ≈ 36%，NVFP4 模式下仅使用 192/352 ≈ 55%。

#### 方法一：运算器阵列复用

**通用场景**：多模式下运算需求不同，高精度模式需要完整运算器，低精度模式仅需子集。

**方法**：按各模式用量的**最大值**实例化每种运算器，通过模式感知的输入切片和索引偏移实现跨模式共享。

**案例（乘法器阵列）**：FP16 需要 4×4 + 4×7 + 7×7 三组子乘法器，FP8 仅需 4×4。

```
乘法器实例化策略（按各模式需求的最大值）:
  P4X4 × 32:  max(FP16=16, FP8=32)     = 32
  P4X7 × 32:  max(FP16=32)              = 32  (ab项[0:15], ba项[16:31])
  P7X7 × 16:  max(FP16=16)              = 16  (仅FP16需要)
```

关键技术点：

| 要点 | 说明 |
|------|------|
| **切片感知模式** | FP16 提取 `[10:7]`hi4 + `[6:0]`lo7；FP8 提取 `[3:0]` 全尾数作 hi4，lo7 置零（乘积自然为 0） |
| **对等信号复用** | ab 项 `hi_a × lo_b` 存于 `[0:15]`，ba 项 `hi_b × lo_a` 存于 `[16:31]`，共享同一组 P4X7 |
| **旁路替代** | 1-bit 尾数乘法（如 NVFP4）用位移加法替代 (`mant + mant>>1`)，不消耗乘法器 |

**效果**：乘法器从 96 个（按最大并行度 × 最大位宽全量实例化）降至 80 个，节省 16 个。

#### 方法二：寄存器位宽复用（位拆分存储）

**通用场景**：高精度模式通道少但位宽大，低精度模式通道多但位宽小。若按最大并行度 × 最大位宽声明寄存器，大量高位闲置。

**方法**：物理寄存器位宽按高精度模式的并行度需求定义，低精度模式下将多个窄位宽数据**打包**存入同一物理槽位。

```
物理寄存器结构:
  PHYS_SLOTS  = 16       (固定槽位数, 对等最大精度模式的通道数)
  PHYS_MANT_W = 11       (每槽位宽)
  PHYS_REG_W  = 176      (物理寄存器总位宽 = 16 × 11)

映射策略:
  FP16模式  (16ch): slot[i][10:0] ← ch[i] 尾数                    → 1:1 直接映射
  FP8模式   (32ch): slot[i][3:0]  ← ch[2i] 尾数, slot[i][7:4]  ← ch[2i+1] 尾数 → 2:1 位拆分
  NVFP4模式 (32ch): slot[i][1:0]  ← ch[2i] 尾数, slot[i][3:2]  ← ch[2i+1] 尾数 → 2:1 位拆分
```

**关键设计模式**：

| 阶段 | 操作 | 位宽 |
|------|------|------|
| **内部处理** | 全格式展开 `MAX_PARALLEL × EXT_MANT_W` | 352 bit（逐通道访问便利） |
| **打包出口** | 按模式压缩为 `PHYS_REG_W` | 176 bit（节省跨级寄存器） |
| **解包入口** | 恢复为内部全格式 | 352 bit（下游逐通道处理） |

**效果**：尾数寄存器从 352 bit 降至 176 bit，跨级寄存器面积节省 50%。

#### 方法论原则

| # | 原则 | 说明 |
|---|------|------|
| 1 | **先分析再设计** | 枚举所有模式的并行度 × 位宽需求矩阵，识别峰值与闲置 |
| 2 | **物理资源定上限** | 寄存器/运算器按合理交集定义上限，非最大值的笛卡尔积 |
| 3 | **打包在出口，解包在入口** | 接口传紧凑格式省寄存器，内部展开全格式便处理 |
| 4 | **参数化声明** | `parameter/localparam` 定义物理规格，支持跨配置裁剪 |
| 5 | **旁路优于虚耗** | 简单运算（位移/加法）可替代时，不做完整运算器实例化 |
| 6 | **对等复用优先** | 两信号位宽与计算模式对等时，索引偏移复用同一组硬件 |

---

## Phase 2: RTL 编码

### 2.1 模块结构模板

```verilog
/*
 * 模块：<模块名>
 * 描述：<功能说明>
 * 流水线阶段：
 *   阶段 0：输入捕获
 *   阶段 1：<描述>
 *   ...
 */

module <模块名> #(
    parameter DATA_WIDTH  = 16,
    parameter NUM_ELEMENTS = 16
) (
    input  wire clk,
    input  wire rst_n,
    input  wire i_enable,
    input  wire [DATA_WIDTH-1:0] i_data,
    output reg  o_idle,
    output reg  [DATA_WIDTH-1:0] o_result
);

    //--- 状态机 ---
    localparam STAGE_IDLE = 0;
    localparam STAGE_0    = 1;
    localparam STAGE_1    = 2;
    localparam STAGE_DONE = 3;
    reg [1:0] state_q;

    //--- 阶段 0 信号 ---
    reg [DATA_WIDTH-1:0] s0_data;

    //--- 阶段 0 组合逻辑 ---
    always @(*) begin
        // 纯组合电路计算
    end

    //--- 阶段 0 时序逻辑 ---
    always @(posedge clk) begin
        if (!rst_n) begin
            s0_data <= {DATA_WIDTH{1'b0}};
        end else if (state_q == STAGE_0) begin
            s0_data <= i_data;
        end
    end

    //--- 输出 ---
    assign o_idle   = (state_q == STAGE_IDLE);
    assign o_result = s0_data;

endmodule
```

### 2.2 关键编码规则

1. **分离组合逻辑与时序逻辑**（Cliff Cummings 黄金法则）
   - 组合：`always @(*)`，阻塞赋值 `=`
   - 时序：`always @(posedge clk)`，非阻塞赋值 `<=`
   - 禁止同一块内混用

2. **`if`/`else` 必须有 `begin-end`**，即使是单行

3. **组合逻辑块默认赋值**防锁存器：
   ```verilog
   always @(*) begin
       result = {WIDTH{1'b0}};  // 默认值 → 所有分支前驱
       if (condition)
           result = ...;
   end
   ```

4. **实例化端口上禁止逻辑运算** — 命名连接 + 直通 wire

5. **总线格式**：统一 `[WIDTH-1:0]`，禁止 `[0:WIDTH-1]`

6. **信号对齐**：按类型、位宽、名称列对齐声明

7. **显式 `signed` 关键字**：Verilog 默认无符号。混合 signed/unsigned 产生不确定结果。用 `$signed()` / `$unsigned()` 显式转换

8. **避免 `casex`**：`casex` 将 `x` 和 `z` 都视为无关位，掩盖仿真问题。优先 `casez`

9. **可变移位/循环左移实现**：优先使用 **桶形移位器（MUX 级联）**，避免全枚举 case。桶形移位器综合后面积最小、时序最优。
   ```verilog
   // 推荐：桶形移位器（MUX 级联）
   // STAGE 4: shift by 16
   wire [31:0] s4 = rot_amt[4] ? {t[15:0], t[31:16]} : t;
   // STAGE 3: shift by 8
   wire [31:0] s3 = rot_amt[3] ? {s4[23:0], s4[31:24]} : s4;
   // STAGE 2: shift by 4
   wire [31:0] s2 = rot_amt[2] ? {s3[27:0], s3[31:28]} : s3;
   // STAGE 1: shift by 2
   wire [31:0] s1 = rot_amt[1] ? {s2[29:0], s2[31:30]} : s2;
   // STAGE 0: shift by 1
   wire [31:0] result = rot_amt[0] ? {s1[30:0], s1[31]} : s1;

   // 避免：32 路全枚举 case — 综合工具展开所有分支，面积大
   function [31:0] rol32;
      input [31:0] x;
      input [4:0] n;
      case (n)
         5'd0: rol32 = x;
         5'd1: rol32 = {x[30:0], x[31]};
         // ... 31 个 case ...
         5'd31: rol32 = {x[0], x[31:1]};
      endcase
   endfunction
   ```

### 2.3 时钟门控策略

**模块级（粗粒度）**：用模块 idle 信号门控整个模块时钟。

```verilog
assign module_clk_en = ~idle;
// 综合工具插入 ICG（Integrated Clock Gating）单元
```

**寄存器级（细粒度）**：`if (enable)` 无 `else` 风格，让综合工具推断自动时钟门控。

```verilog
// 正确：if-only → 综合工具推断 ICG。enable=0 时 FF 保持原值
always @(posedge clk) begin
    if (enable) begin
        data_q <= data_in;
    end
end

// 错误：if-else → 综合工具无法推断时钟门控
always @(posedge clk) begin
    if (enable) begin
        data_q <= data_in;
    end else begin
        data_q <= data_q;  // 显式保持 → 阻止 ICG 插入
    end
end
```

**原理**：综合工具识别到 `enable=0` 时寄存器保持原值，自动将数据通路 MUX 替换为时钟通路 ICG 单元（基于锁存器防毛刺结构），节省时钟树和数据通路双重动态功耗。

**规则：**
1. 禁止 AND/OR 门手动门控时钟 — 用 ICG 或让综合推断
2. 模块级门控用 idle 信号做粗粒度
3. 寄存器级门控用 `if (enable)` 风格做细粒度
4. CE 信号必须与门控时钟域同步
5. CE 信号在模块内本地生成，避免跨模块时序问题

### 2.4 单一加法器树：XOR 二进制补码

累加有符号值时，避免同一循环中同时用 `+` 和 `-`。每个运算符综合出独立的加法器树，面积和功耗翻倍。

```verilog
// 错误：if/else ± → 两个独立加法器树
always @(*) begin
    sum = 0;
    for (i = 0; i < N; i = i + 1) begin
        if (sign[i])
            sum = sum - val[i];  // 减法器树
        else
            sum = sum + val[i];  // 加法器树
    end
end

// 正确：XOR 二进制补码 → 单一加法器树
// sign=0: val ^ 0 + 0 = +val
// sign=1: val ^ 1 + 1 = ~val + 1 = -val
assign signed_val[i] = (val[i] ^ {W{sign[i]}}) + sign[i];

always @(*) begin
    sum = 0;
    for (i = 0; i < N; i = i + 1) begin
        sum = sum + signed_val[i];  // 单一加法器树
    end
end
```

### 2.5 消除不必要条件分支

每个条件分支增加 MUX 逻辑。当条件在数学上必然成立时，直接移除分支。

```verilog
// 错误：不必要的条件 — max_exp = max(exp_prod[])，无元素能超过它
if (exp_prod[i] < max_exp)
    aligned[i] = mant[i] >> (max_exp - exp_prod[i]);
else
    aligned[i] = mant[i];  // 等同于 >> 0，多余 MUX

// 正确：始终右移，差值为 0 时移位量为 0，等价空操作
aligned[i] = mant[i] >> (max_exp - exp_prod[i]);
```

### 2.6 原生格式输出

最后一流水级直接输出最终格式，禁止在流水线之后加独立后处理转换。消除冗余转换逻辑，保持全精度无中间截断。

```verilog
// 错误：流水线输出 FP16 → 独立组合逻辑块转 FP32
result_fp16 <= s5_result;
assign fp32_result = {result_fp16[15], result_fp16[14:10] + 112, result_fp16[9:0], 13'b0};

// 正确：最后一流水级直接输出 FP32
result <= s5_result;  // 已是 FP32 位宽格式
```

---

## Phase 3: 数值系统

### 3.1 核心原则：设计者掌控数值系统

**在 Verilog 中，所有 bit 只是电平。** bit 的含义（有符号/无符号/定点/偏移指数）存在于设计者脑中，不在语言中。必须：

1. 编码前明确定义每个位域的数值表示、偏移量、有效范围
2. 每次运算后跟踪结果的数值表示和有效范围
3. 每个边界做显式越界保护，不依赖回绕行为

### 3.2 位宽审计

每次算术运算必须审计位宽：

| 运算 | 结果位宽 | 原因 |
|------|---------|------|
| 加法 `a + b` | `max(Wa, Wb) + 1` | 进位位 |
| 乘法 `a × b` | `Wa + Wb` | 最大乘积位宽 |
| 减法 `a - b` | `max(Wa, Wb) + 1` | 符号/借位位 |

截断静默丢弃高位。务必验证结果适合目标容器。

```verilog
// 危险：22 位乘积赋给 20 位容器 → 高 2 位截断
aligned = mant_prod << (20 - shift_amt);

// 安全：右移保持有效位在容器内
aligned = mant_prod >> shift_amt;
```

### 3.3 减法下溢保护

无符号减法可能下溢回绕。必须预判数学可能为负的情况并显式保护：

```verilog
if ({1'b0, exp_a} + {1'b0, exp_b} < {1'b0, BIAS}) begin
    exp_prod = 0;  // 数学结果为负 → 钳位到零
end else begin
    exp_prod = exp_a + exp_b - BIAS;
end
```

### 3.4 二进制补码取反：位宽陷阱

补码取反 `~x + 1` 必须在原始位宽下操作，禁止先扩展再取反。

```verilog
// 正确：原始位宽取反，再符号扩展
neg_value = ~aligned + 1'b1;

// 错误：先扩展再取反 → aligned=0 时结果 = 2^N ≠ 0
neg_value = {1'b0, ~aligned} + 1'b1;
```

边界情况：最小可表示负数（如 8 位 `-128 = 10000000`）取反 = 自身，需特殊处理。

### 3.5 符号位检查顺序

当无符号算术结果在数学上可能为负时，做范围比较**之前**必须检查 MSB 符号位。

```verilog
// 正确：先检查符号位（下溢），再检查正溢出
if (exp_final[MSB])
    → Zero;                       // 负数 → 下溢
else if (exp_final >= 31)
    → Infinity;                   // 正溢出

// 错误：先做范围比较 → 负值当大正数
if (exp_final >= 31)
    → Infinity;                   // exp_final = -9 → 无符号 119 → 误判！
```

### 3.6 前导 1 检测

```verilog
function [7:0] find_leading_one;
    input [WIDTH-1:0] data;
    integer j;
    integer found;
    begin
        find_leading_one = 0;
        found = 0;
        for (j = WIDTH-1; j >= 0; j = j - 1) begin
            if ((found == 0) && data[j]) begin
                find_leading_one = j[7:0];
                found = 1;  // 锁定第一个检测到的置位 bit
            end
        end
    end
endfunction
```

`found` 标志防止循环继续返回低位置位 bit。

### 3.7 浮点指数偏移跟踪

在浮点流水线中，指数表示每级演变。设计者必须跟踪每级残余偏移量。

**FP16 点积流水线案例：**

```
阶段 2：exp_prod = e_a + e_b - FP16_BIAS        → 残余偏移 +15
阶段 3：max_exp = max(exp_prod[])                → 残余偏移 +15
阶段 5：exp_unbiased = max_exp + leading_pos     → 移除 FP16_BIAS → 真无偏
                      - FRAC_BITS - FP16_BIAS
FP32 输出：exp_biased = exp_unbiased + FP32_BIAS → 加 127 偏移
```

```verilog
// 错误：漏减 FP16_BIAS
s5_exp = max_exp + leading_pos - FRAC_BITS;  // 少了 15

// 正确：减掉所有累积偏移
s5_exp_unb = max_exp + leading_pos - FRAC_BITS - FP16_BIAS;
```

### 3.8 FP16 算术

#### 3.8.1 特殊值处理

IEEE 754 FP16 特殊值编码：

| exp[4:0] | mant[9:0] | 含义 |
|----------|-----------|------|
| 0 | 0 | 零（有符号 ±0） |
| 0 | ≠0 | 次正规数 |
| 1~30 | 任意 | 规格化数 = (-1)^s × 1.mant × 2^(exp-15) |
| 31 | 0 | 无穷大 ±∞ |
| 31 | ≠0 | NaN |

```verilog
s1_is_zero  = (exp == 0) && (mant == 0);
s1_is_sub   = (exp == 0) && (mant != 0);
s1_is_inf   = (exp == 31) && (mant == 0);
s1_is_nan   = (exp == 31) && (mant != 0);

// 次正规数当零处理（面积/性能 vs 精度权衡）
s1_mant_ext = s1_is_sub ? {1'b0, mant} : {1'b1, mant};
```

#### 次正规数：隐含前导位差异

```verilog
// 正确：次正规数隐含 0，规格化数隐含 1
ext_mant = ((exp == 0) && (mant != 0))
         ? {1'b0, mant}  // 次正规：0.mant
         : {1'b1, mant}; // 规格化：1.mant

// 次正规有效指数 = 1（非 0！），IEEE 754 规定 E = 1 - BIAS
eff_exp = ((exp == 0) && (mant != 0)) ? 1 : exp;
```

#### 3.8.3 单路径指数计算

```verilog
// 错误：运行时分支产生两条并行数据路径
s5_exp = max_exp - FP16_BIAS;
if (leading_pos > FRAC_BITS)
    s5_exp = s5_exp + (leading_pos - FRAC_BITS);

// 正确：单条算术路径。leading_pos == FRAC_BITS 时加 0，等价空操作
s5_exp = max_exp + leading_pos - FRAC_BITS - FP16_BIAS;
```

---

## Phase 4: 测试平台

### 4.1 自检测试平台要素

1. **FIFO 暂存器**：捕获输入供后续交叉检查
2. **参数化**：与 DUT 共享同一套参数集（`include` 或 package）
3. **多模式覆盖**：FP16、INT16、混合等
4. **可重现随机**：`$urandom(seed)` 固定种子
5. **自动评分**：通过/失败报告，不依赖手动波形检查
6. **延迟用 `repeat(N)`**：确保 FSDB 波形时间戳对齐。`#delay` 不产生时间戳边界

**强制**：DUT 和 TB 必须共享同一套参数定义。禁止参数重复声明。

### 4.2 竞争条件诊断

当仿真在以下语句挂起或给出错误结果：
```verilog
scb_dout = tmp_dout[(multi_index + 1) * DATA_WIDTH - 1 -: DATA_WIDTH];
```

根因：在数据字完成下一次乘累加之前读取了它。

解决：
```verilog
// 方案 A：注入前清除暂存队列
scb_q.delete(scb_index);

// 方案 B：流水线满时同期捕获
scb_dout = tmp_dout[(scb_index + 1) * DATA_WIDTH - 1 -: DATA_WIDTH];
```

### 4.3 参数化验证与交叉验证

```verilog
parameter NUM_ELEMENTS = 16;
parameter INT16_BITS    = 16;

reg  [INT16_BITS-1:0] a_vec [0:NUM_ELEMENTS-1];
reg  [INT16_BITS-1:0] b_vec [0:NUM_ELEMENTS-1];

for (i = 0; i < NUM_ELEMENTS; i = i + 1) begin
    a_vec[i] = $urandom(seed);
    b_vec[i] = $urandom(seed);
end
```

DUT 输出 INT16，参考模型输出 FP32 时的交叉验证：
```verilog
$signed({scb_result, {1{1'b0}}})  // INT16 扩展为有符号 32 位
```

### 4.4 测试向量覆盖要求

单一测试向量不足以验证正确性。**至少覆盖以下场景：**

| 类型 | 说明 | 示例 |
|------|------|------|
| **标准测试向量** | 算法/协议标准中给出的官方测试用例 | SM3 的 "abc" 测试向量、IEEE 754 特殊值 |
| **边界长度** | 空消息、单字节、最大块长度、非整数块 | SHA-256 的空消息 hash、块边界对齐 |
| **多块链式** | 连续两笔以上数据，验证流水线状态保持和链式迭代 | 多块 hash 链式、连续浮点运算 |
| **边界值** | 最大值、最小值、零、溢出/下溢 | FP16 的 INF/NaN、有符号 INT16 的 -32768 |
| **随机测试** | 大量随机输入交叉验证（DUT vs 参考模型） | `$urandom(seed)` 生成千级测试 |

### 4.5 调试打印方法学

自检测试平台（Self-Checking Testbench）不仅依赖波形分析，更需要结构化的调试打印体系。以下方法学提炼自工业级混合精度点积引擎的 7 个测试模块实践。

#### 4.5.1 核心组件

每个测试模块应包含以下标准组件：

| 组件 | 类型 | 说明 |
|------|------|------|
| `pass_count` / `fail_count` | `integer` | 全局通过/失败计数器，仿真结束时输出汇总 |
| `cycle` (可选) | `integer` | 周期计数器，用于调试打印的时间戳标注 |
| `wait_timeout` | `integer` | 超时等待计数器，防止仿真死锁 |
| `check_*` task(s) | `task` | 结果验证任务，自动比对期望值与实际输出 |
| `fill_*` function(s) | `function` | 输入填充函数，快速构造不同格式的测试向量 |
| `init_*` / `set_*` task(s) | `task` | 初始化/设置任务，统一管理信号赋值 |

```verilog
// ── 标准声明模板 ──
integer pass_count;
integer fail_count;
integer wait_timeout;

// ── 周期计数器（需要时）──
integer cycle;
always @(posedge clk) begin
    cycle = cycle + 1;
end
```

#### 4.5.2 测试组织结构

采用**分层测试结构**，清晰区分测试阶段：

```
=== TEST N: <描述> ===        ← 测试标题横幅
[DBG] time=<时间戳>            ← 可选的调试信息
  [PASS] <test_name>          ← 成功项
  [FAIL] <test_name>          ← 失败项（含期望值 vs 实际值）
=== Summary: Pass=X, Fail=Y === ← 测试汇总
```

**标题横幅格式**：

```verilog
// ── 顶层测试标题 ──
$display("=== TEST 1: FP16×FP16, 4PE all 1.0*1.0 -> 64.0 ===");

// ── 子测试分区标题 ──
$display("--- Directed: FP16xFP16 N=1 ---");
$display("--- PART 1: NVFP4 Tag Detection (8 encodings) ---");
```

**命名规范**：

- 顶层测试标题：`=== TEST <N>: <模式> <输入描述> -> <期望输出> ===`
- 分区标题：`--- <分区名>: <描述> ---`
- 子测试标题：`<缩写>: <描述>`（如 `D1: FP16 16ch×1.0 N=1`、`RAND FP16xFP16 seed=0`）

#### 4.5.3 结果验证 Task 模式

##### 模式 A：通用比对 Task（端到端验证）

适用于输出可直接比对期望值的场景：

```verilog
task check_result;
    input [31:0] expected;
    input [255:0] test_name;
    begin
        if (result_fp32[31:0] === expected) begin
            pass_count = pass_count + 1;
            $display("[PASS] %0s: got=0x%08X, expected=0x%08X", test_name, result_fp32, expected);
        end else begin
            fail_count = fail_count + 1;
            $display("[FAIL] %0s: got=0x%08X, expected=0x%08X", test_name, result_fp32, expected);
        end
    end
endtask
```

**关键设计点**：
- 同时打印实际值和期望值的十六进制表示，方便直接比对 bit pattern
- `[PASS]`/`[FAIL]` 前缀便于日志 grep 筛选
- 输入参数支持不同位宽的期望值（`input [31:0]`、`input [MANT_PROD_W-1:0]`）

##### 模式 B：Golden Model 比对 Task（中间级验证）

适用于需要软件参考模型计算期望值的场景：

```verilog
task check_s2_channel;
    input [5:0]  ch_idx;
    input string  test_name;
    reg [MANT_PROD_W-1:0] golden_mant;
    begin
        // 用 golden 函数计算期望值
        golden_mant = golden_mant_prod(mode, phys_a, phys_b, sub);
        // 逐字段比对
        if (mant_prod[ch_idx*MANT_PROD_W +: MANT_PROD_W] === golden_mant &&
            exp_sum[ch_idx*EXP_SUM_W +: EXP_SUM_W] === golden_exp &&
            sign_prod[ch_idx] === golden_sign) begin
            pass_count = pass_count + 1;
        end else begin
            fail_count = fail_count + 1;
            $display("  [FAIL] %0s ch=%0d: mant=%0d(golden=%0d) exp=%0d(golden=%0d) sign=%b(golden=%b)",
                     test_name, ch_idx,
                     mant_prod[ch_idx*MANT_PROD_W +: MANT_PROD_W], golden_mant,
                     exp_sum[ch_idx*EXP_SUM_W +: EXP_SUM_W], golden_exp,
                     sign_prod[ch_idx], golden_sign);
        end
    end
endtask
```

**关键设计点**：
- golden （黄金参考）函数与 RTL 逻辑完全对齐，两者独立开发
- 失败时打印所有差异字段，便于快速定位根因
- channel 级粒度便于隔离故障通道

##### 模式 C：信号存在性检查

适用于仅需验证信号是否触发（非精确值）的场景：

```verilog
task check_non_zero;
    input [2:0]  lane_n;
    input string test_name;
    begin
        if ($signed(tree_sum[CSW*lane_n +: CSW]) != 0 && local_valid[lane_n] === 1'b1) begin
            pass_count = pass_count + 1;
            $display("  [PASS] %0s (lane%0d): tree_sum=%0d", test_name, lane_n,
                     $signed(tree_sum[CSW*lane_n +: CSW]));
        end else begin
            fail_count = fail_count + 1;
            $display("  [FAIL] %0s (lane%0d): tree_sum=%0d, valid=%b",
                     test_name, lane_n,
                     $signed(tree_sum[CSW*lane_n +: CSW]), local_valid[lane_n]);
        end
    end
endtask
```

#### 4.5.4 超时保护模式

每个等待外部信号的循环必须带有超时保护，防止仿真无限挂起：

```verilog
task wait_out_valid;
    begin
        wait_timeout = 0;
        while (!out_valid && wait_timeout < 50) begin
            @(posedge clk);
            wait_timeout = wait_timeout + 1;
        end
        if (!out_valid) begin
            fail_count = fail_count + 1;
            $display("[FAIL] out_valid not asserted after %0d cycles", wait_timeout);
        end
    end
endtask
```

**超时阈值选择原则**：
| 场景 | 推荐阈值 | 说明 |
|------|---------|------|
| 单路流水线输出等待 | 30 cycles | 覆盖最坏情况延迟 + 50% 裕量 |
| 多 PE 级联排空 | 30 cycles | 覆盖级联传播延迟 |
| 复杂模块输出等待 | 50 cycles | 预留异常情况裕量 |
| 随机测试批量等待 | 100 cycles | 大量数据注入时放宽 |

#### 4.5.5 调试监控模式

##### 条件触发监控（早期开发阶段）

在开发初期，通过`always @(negedge clk)`加周期范围限制，密集打印关键内部信号：

```verilog
// ── 开发调试：前 50 个周期密集监控 ──
always @(negedge clk) begin
    if (cycle > 0 && cycle <= 50) begin
        $display("DEBUG cycle=%0d: in_ready=%b in_valid=%b out_valid=%b",
                 cycle, in_ready, in_valid, out_valid);
        $display("  pe0 pipe_valid=%b pe1 pipe_valid=%b pe2 pipe_valid=%b pe3 pipe_valid=%b",
                 u_pe_group.pe_inst[0].u_dp.pipe_valid,
                 u_pe_group.pe_inst[1].u_dp.pipe_valid,
                 u_pe_group.pe_inst[2].u_dp.pipe_valid,
                 u_pe_group.pe_inst[3].u_dp.pipe_valid);
    end
end
```

**使用原则**：
- 仅在开发早期启用，正式验证时应注释或移除
- 通过分层打印组织信号：控制信号 → 数据信号 → 状态标志
- 使用 DUT 层级路径访问内部信号（`u_pe_group.pe_inst[0].u_dp.pipe_valid`）

##### 内联调试打印（定向测试中）

在定向测试 Task 内部直接插入调试打印：

```verilog
$display("    [S1-debug] nvfp4=0x%h exp_eff_a[ch0]=%0d ext_mant_a[slot0]=11'b%011b",
         nvfp4_code,
         exp_eff_a[0 +: EXP_EFF_W],
         ext_mant_a[0 +: EXT_MANT_W]);
```

**命名约定**：`[模块名-debug]` 前缀，便于 grep 筛选和事后清理。

#### 4.5.6 随机测试打印规范

随机测试需要记录种子值以便复现：

```verilog
$display("  [PASS] RAND %0s seed=%0d (lane%0d): tree_sum=%0d, max_exp=%0d",
         mode_name, seed, lane_n, $signed(tree_sum), golden_max);
```

- 失败时**必须打印种子值**，否则无法复现
- 成功时可选择性打印，减少日志量
- 使用 `$sformatf` 动态构造测试名称

#### 4.5.7 仿真最终汇总

每个测试模块在 `$finish` 前必须输出汇总报告：

```verilog
$display("============================================");
$display("  %s Summary: Pass=%0d, Fail=%0d, Total=%0d",
         test_module_name, pass_count, fail_count, pass_count + fail_count);
$display("============================================");
```

**质量标准**：
- 所有 Testbench 的 `pass_count` 必须等于 `total_count`（fail_count = 0）
- 不得存在未检测的 PASS/FAIL（所有检查路径必须通过 check task）

#### 4.5.8 波形导出规范

```verilog
initial begin
    $dumpfile("build/sim_<module>.vcd");
    $dumpvars(0, tb_<module>);  // 0=捕获所有层级
end
```

- VCD 文件统一输出到 `build/` 目录
- 命名与 testbench 模块名对应（`sim_pe_group.vcd`）
- `$dumpvars(0, ...)` 捕获所有层级信号，调试阶段不建议限制层级

#### 4.5.9 调试打印生命周期

```
开发早期 →
  条件触发监控 (always @(negedge clk) + cycle 范围)
  定向测试 + Golden Model 比对
  ↓
验证阶段 →
  移除/注释条件触发监控
  保留所有 check_* task (定向 + 随机)
  完整随机测试覆盖
  ↓
回归测试 →
  仅保留 pass/fail 汇总
  check_* task 内部可省略 PASS 打印（仅打印 FAIL）
```

#### 4.5.10 实战案例：混合精度点积引擎验证体系

以下数据来自 `dot_product_pipeline` 项目 7 个测试模块的实际验证结果。

##### 测试模块清单

| 模块 | 测试类型 | 覆盖范围 | 打印模式 |
|------|---------|---------|---------|
| `tb_pe_group` | 定向 + 随机 | PE 级联流水线全路径 | 模式 A + B + C |
| `tb_dot_product_pipeline` | 端到端 | 4PE × 多模式，含级联 | 模式 A + 超时 |
| `tb_s1_spv_format_expand` | 中间级 + 随机 | 7 种格式展开，golden 比对 | 模式 B |
| `tb_s2_multiplier_array` | 中间级 + 随机 | 288 atom 乘法器阵列 | 模式 B |
| `tb_s3_align_adder_normalize` | 中间级 | 对齐加法归一化流水线 | 模式 B |
| `tb_s4_cascade_accum` | 中间级 | 级联累加 + overflow 检测 | 模式 A + C |
| `tb_nvfp4` | 格式专项 | NVFP4 8 种编码检测 | 模式 B |

##### 验证覆盖率

| 维度 | 覆盖率 | 说明 |
|------|--------|------|
| 运算模式 | 7/7 (100%) | FP16×FP16, INT8×INT8, FP8×FP16, FP8×FP8, NVFP4×FP16, NVFP4×FP8, NVFP4×NVFP4 |
| 通道组合 | 4/8/16/32 | 覆盖 N=1/2/4 正交组合 |
| 级联路径 | 已覆盖 | cascade_in/out 跨 PE 传播 |
| 边界条件 | 已覆盖 | subnormal、零值、溢出、最大/最小指数 |
| 随机种子 | 多组 | 每个模式的定向测试后附加随机回测 |

##### 打印日志量管理策略

- **开发期**：`[DBG]` 前缀 + `always @(negedge clk)` 条件监控，限制 cycle ≤ 50
- **验证期**：仅 `[PASS]`/`[FAIL]` 打印，`[DBG]` 全部注释
- **回归期**：`[PASS]` 聚合为计数，仅 `[FAIL]` 详细打印
- **定位技巧**：`grep FAIL build/sim_*.txt` 一键汇总所有失败项

---

## Phase 5: 调试技术

### 5.1 波形分析要点

- 优先 `.fsdb`（Verdi 格式）：体积小、加载快、支持层次化导航
- `fsdbDumpvars(0, dut_top, "+all")`：捕获所有信号
- `fsdbDumpMDA(0, dut_top, 1)`：捕获多维数组
- 信号平坦/不活跃时：`repeat(N)` 产生时间戳边界，`#delay` 不产生。补 `@(posedge clk)` 同步点

### 5.2 调试流程

```
1. 观察 DUT 输出 → 确认数据按时到达
2. 计算预期值 → 与已知正确行为交叉检查
3. 隔离输入源 → 排除上游损坏
4. 二进制搜索 → 定位出错 bit 位
5. 检查运算顺序 → 验证符号位解释
```

### 5.3 常见混淆点

- `reg [15:0]` 默认为无符号 → 始终验证 `$signed()` 转换
- `generate for` 中的 `integer` 变量阴影 → 用不同标识符
- 偏移量可变时用 `[MSB -: WIDTH]`，不用 `[WIDTH-1:0]`

---

## Phase 6: 风格与最佳实践

### 6.1 信号命名约定

| 流水级 | 组合逻辑信号 | 时序寄存器 |
|--------|-------------|-----------|
| 0 | `stage_0_X` | `s0_X` |
| 1 | `stage_1_X` | `s1_X` |
| N | `stage_N_X` | `sN_X` |

- `sN_` = 第 N 级时序寄存器输出
- `i_` = 模块输入端口
- `o_` = 模块输出端口
- `_q` 后缀 = 弃用的旧寄存器（重构过渡）

#### 信号命名基本准则

| 准则 | 说明 |
|------|------|
| **禁止无意义短名** | 禁止单字母或 ≤3 字符且含义不明确的信号名，如 `tmp`、`arr`、`sig` |
| **语义必须清晰** | 信号名应准确反映功能和用途，如 `fifo_wr_en`（可读）|
| **循环变量例外** | `for` 循环中的生成变量 `i`、`j`、`k` 允许单字母，但 loop 体内部信号仍须有语义名 |
| **测试平台例外** | 测试平台中的临时比对变量可接受简短名，但必须注释说明用途 |
| **避免缩写歧义** | 通用缩写允许（`en`=enable, `addr`=address, `clk`=clock, `rst`=reset），自定义缩写须在文件头注释说明 |
| **名称长度** | 推荐 8~40 字符。太短语义不足，太长影响波形阅读 |

**正确示例**：`fifo_wr_en`、`alu_result_valid`、`stage_2_accum`、`i_axis_tdata`、`o_mem_wdata`

**错误示例**：`a`、`sig`、`tmp`、`d`、`reg1`、`arr`（缩写难以猜测）

#### 流水级命名

### 6.2 代码组织

```verilog
// ============ 模块：<name> ============

// 阶段 0：输入捕获
// --- 组合逻辑 ---
// --- 时序逻辑（寄存器） ---

// 阶段 1：<描述>
// --- 组合逻辑 ---
// --- 时序逻辑（寄存器） ---

// 阶段 N：最终输出
```

### 6.3 注释标准

```verilog
/*
 * 文件：<name>.v
 * 项目：<project>
 * 描述：<功能描述>
 *
 * 流水线阶段：
 *   阶段 0：输入捕获
 *   阶段 1：<描述>
 *   ...
 *
 * 架构说明：
 *   - <设计决策>
 *
 * 参考：<IEEE 754 等标准>
 */
```

---

## Phase 7: 综合与物理设计

### 7.1 开源 EDA 工具链（Windows + WSL）

所有开源 EDA 工具均为 Linux 原生。Windows 下通过 WSL 运行：

```powershell
# 仿真：先清理缓存/临时文件，再编译运行
wsl bash -c "make sim-clean && make sim"

# 查看波形（GTKWave 需在 WSL 内安装）
wsl bash -c "make wave"

# 综合
wsl bash -c "make synth"
```

工具链：

```
仿真        → Icarus Verilog (iverilog) + vvp
波形        → GTKWave (VCD) / Verdi (FSDB)
综合        → Yosys + OpenSTA
布局布线    → OpenROAD
逻辑等价性  → Yosys (equiv_*)
```

#### 标准项目目录结构

```
project/
├── Makefile            # 仿真/综合/清理命令
├── params.vh           # 全局参数定义
├── rtl/                # RTL 源文件
│   ├── fifo.v
│   └── top_module.v
├── tb/                 # 测试平台
│   ├── tb_top.v
│   └── tb_utils.vh
├── syn/                # 综合输出（gitignore）
│   └── syn_output.v
├── sim/                # 仿真输出（gitignore）
│   ├── simv            # 编译的仿真可执行文件
│   └── dump.vcd        # 波形文件
└── scripts/
    ├── sta.tcl         # 时序分析脚本
    └── yosys.tcl       # 综合脚本
```

### 7.2 Yosys 综合脚本

```tcl
read_verilog -sv params.vh
read_verilog -sv rtl/dut.v
hierarchy -top top_module
proc; memory -nomap
techmap; flatten
abc -liberty sky130_fd_sc_hd__tt_025C_1v80.lib
opt
stat -width
write_verilog -noattr syn_output.v
```

### 7.3 时序约束（OpenSTA）

```tcl
read_liberty sky130_fd_sc_hd__tt_025C_1v80.lib
read_verilog syn_output.v
link_design top_module
create_clock -period 2.0 [get_ports clk]
set_input_delay  -clock clk 0.5 [all_inputs]
set_output_delay -clock clk 0.5 [all_outputs]
report_checks
```

### 7.4 Makefile 集成（WSL + iverilog）

```makefile
# Makefile - Verilog 仿真/综合（WSL + iverilog + Yosys）
# 使用： powershell 执行 `wsl bash -c "make sim"`
#       powershell 执行 `wsl bash -c "make sim-clean && make sim"`

# ─── 项目路径 ───────────────────────────────
RTL_DIR    := rtl
TB_DIR     := tb
SIM_DIR    := sim
VERILOG_SOURCES := $(wildcard $(RTL_DIR)/*.v) params.vh
TESTBENCH  := $(TB_DIR)/tb_top.v
SIMV       := $(SIM_DIR)/simv
WAVE       := $(SIM_DIR)/dump.vcd

# ─── 编译选项 ───────────────────────────────
VFLAGS     := -g2012 -Wall
VFLAGS     += -I$(RTL_DIR) -I$(TB_DIR)

# ─── 仿真（依赖清理） ────────────────────────
.PHONY: sim sim-clean clean wave

sim: $(SIMV)
	vvp $(SIMV)

$(SIMV): $(VERILOG_SOURCES) $(TESTBENCH) | $(SIM_DIR)
	iverilog $(VFLAGS) -o $@ $(VERILOG_SOURCES) $(TESTBENCH)

$(SIM_DIR):
	mkdir -p $@

# ─── 清理 ────────────────────────────────────
# 清理仿真生成文件：可执行文件、波形、运行时临时文件
sim-clean:
	rm -f $(SIMV) $(WAVE) $(SIM_DIR)/*.lxt $(SIM_DIR)/*.lxt2
	rm -rf $(SIM_DIR)/vvp.tmp $(SIM_DIR)/.vvp_tmp

clean:
	rm -rf $(SIM_DIR)

# ─── 波形查看 ────────────────────────────────
wave: $(WAVE)
	gtkwave $(WAVE)

# ─── 综合 ────────────────────────────────────
syn: $(VERILOG_SOURCES)
	yosys -p "read_verilog -sv params.vh $(RTL_DIR)/dut.v; \
	          hierarchy -top top_module; proc; opt; stat; \
	          write_verilog syn/output.v"

sta: syn/output.v
	sta scripts/sta.tcl
```

#### Makefile 使用说明

| 目标 | 命令（WSL 内） | 用途 |
|------|---------------|------|
| `sim` | `make sim` | 先编译 `.v` → `simv`，再运行 `vvp` |
| `sim-clean` | `make sim-clean && make sim` | 清理 `simv` + `*.vcd` + 临时文件再仿真 |
| `clean` | `make clean` | 删除整个 `sim/` 目录 |
| `wave` | `make wave` | 用 GTKWave 打开最新波形 |
| `syn` | `make syn` | Yosys 综合 |

> **为什么不把 `sim-clean` 放在 `sim` 的依赖里？**  
> 前置清理会**每次都重新编译**（增量编译失效），开发迭代中期频繁改少量代码时应避免。  
> 需要清理时显式执行 `make sim-clean && make sim`，或脚本中统一加清理。
>
> **哪些文件需要清理？**  
> - `simv` — 编译的仿真可执行文件（iverilog 输出）  
> - `*.vcd` / `*.lxt` / `*.lxt2` — 波形 dump 文件  
> - `vvp.tmp` / `.vvp_tmp` — vvp 运行时生成的临时文件  
> - `*.o` — 如果使用了 C 模型（PLI/VPI 扩展）

### 7.5 SDC/CDC 检查方法学

基于 Yosys + OpenSTA + Verible 工具链的系统化设计检查方法，覆盖 Lint（代码规范）、Synthesis（综合）、STA（静态时序分析）和 CDC（跨时钟域）四个维度。

#### 7.5.1 工具链概览

| 工具 | 用途 | 安装方式 | 输出 |
|------|------|---------|------|
| **Verible** | Verilog/SystemVerilog Lint 检查，代码风格与语法规范 | 预编译二进制 `verible-verilog-lint` | Lint 报告（结构化文本） |
| **Yosys** | RTL 综合、逻辑优化、网表生成 | `apt-get install yosys` | 综合网表 + 面积/时序报告 |
| **OpenSTA** | 静态时序分析（STA），SDC 约束验证 | 源码编译 / AppImage | 时序违例报告、路径分析 |
| **Icarus Verilog** | 仿真验证 | `apt-get install iverilog` | VCD 波形 |

**工具版本要求**：

| 工具 | 最低版本 | 推荐版本 | 验证方式 |
|------|---------|---------|---------|
| Verible | v0.0-3xxx | v0.0-4071+ | `verible-verilog-lint --version` |
| Yosys | 0.9 | 0.27+ | `yosys --version` |
| OpenSTA | 2.2.0 | 2.2.0+ | `sta -version` |
| Icarus Verilog | 10.0 | 11.0+ | `iverilog -V` |

#### 7.5.2 Verible Lint 检查

##### 基础用法

```bash
# 单文件检查
verible-verilog-lint rtl/dut_top.v

# 批量检查（推荐使用 --rules 指定规则集）
verible-verilog-lint \
  --rules=-no-tabs,-line-length \
  rtl/*.v rtl/*.sv

# 项目级检查（生成结构化报告）
verible-verilog-lint \
  --ruleset=all \
  --generate_output \
  rtl/*.v rtl/*.sv \
  2>&1 | tee build/lint_report.txt
```

##### 推荐 Lint 规则集

以下规则集适用于工业级 RTL 设计：

```bash
# 基础必检规则
REQUIRED_RULES="\
  --rules=+module-begin-block \
  --rules=+explicit-task-return-type \
  --rules=+explicit-function-return-type \
  --rules=+always-comb \
  --rules=+forbidden-macro \
  --rules=+for-loop-index-word-size \
  --rules=+generate-label \
  --rules=+packed-dimensions-range-ordering \
  --rules=+parameter-name-style \
  --rules=+undersized-binary-literal \
  --rules=+unpacked-dimensions-range-ordering \
  --rules=+v2001-generate-begin \
  --rules=+genvar-declaration-in-loop"

# 代码风格规则
STYLE_RULES="\
  --rules=+no-tabs \
  --rules=+line-length=120 \
  --rules=+posix-eof \
  --rules=+trailing-spaces"
```

##### Lint 检查流程

```
Step 1: 准备文件列表 → all_rtl_files.txt
Step 2: 逐文件 Lint → verible-verilog-lint --ruleset=all rtl/module.v
Step 3: 分类问题 → Error（必须修复）/ Warning（建议修复）/ Style（风格建议）
Step 4: 修复 → 按优先级逐一修复，每次修复后重新 Lint 确认
Step 5: 归档 → 保存 Lint 报告到 build/lint_report.txt
```

##### 常见 Lint 问题与修复

| 问题 | Verible 规则 | 原因 | 修复 |
|------|------------|------|------|
| `generate` 块缺少 label | `generate-label` | 未命名的 generate 块 | 添加 `genvar` 及 `begin : label` |
| Tab 字符 | `no-tabs` | 混用 Tab 和空格缩进 | 统一为空格缩进 |
| 文件末尾无换行 | `posix-eof` | POSIX 标准要求 | 文件末尾添加空行 |
| `always @*` 应改为 `always_comb` | `always-comb` | SV 最佳实践 | 替换为 `always_comb` |
| 宏定义使用 | `forbidden-macro` | 宏滥用增加调试难度 | 改用 `localparam` / `function` |
| 二进制常量位宽不足 | `undersized-binary-literal` | `'b1` 未指定位宽 | 改为 `1'b1` |

##### 持续集成集成

```makefile
# Makefile 片段
LINT_FILES := $(shell find rtl -name '*.v' -o -name '*.sv')

.PHONY: lint
lint:
  @echo "=== Verible Lint Check ==="
  @verible-verilog-lint --ruleset=all $(LINT_FILES) 2>&1 | tee build/lint_report.txt || true
  @echo "Lint report saved to build/lint_report.txt"
```

#### 7.5.3 Yosys 综合检查

##### 基础综合脚本

```tcl
# syn.ys — Yosys 综合脚本
# 读取设计文件
read_verilog -sv params.vh
read_verilog -sv rtl/dut_top.v
read_verilog rtl/sub_module.v

# 建立层次结构
hierarchy -check -top dut_top

# 工艺无关优化流程
proc; opt; fsm; opt; memory; opt

# 技术映射（使用内置标准单元库）
techmap; opt

# 报告
stat
stat -width

# 写网表
write_verilog -noattr build/dut_syn.v
```

##### 命令行执行

```bash
# WSL 环境
yosys syn.ys

# 完整综合流程（含 SDC 约束注入）
yosys -p "
  read_verilog -sv params.vh rtl/*.v;
  hierarchy -check -top dot_product_pipeline;
  proc; opt; fsm; opt;
  techmap; opt;
  abc -liberty \$LIBERTY;
  stat -width;
  write_verilog build/dut_syn.v
"
```

##### 综合质量检查清单

| 检查项 | Yosys 命令 | 通过标准 |
|--------|-----------|---------|
| 模块层次完整性 | `hierarchy -check` | 无未解析的模块引用 |
| Latch 检查 | `proc` 后查看警告 | 无 "found latch" 警告 |
| 组合逻辑环路检测 | `opt` 后检查 | 无组合环路 |
| 面积估算 | `stat` | 面积在预期范围内 |
| 多驱动检查 | `check` | 无多驱动信号 |

##### 常见综合问题

| 问题 | 现象 | 根因 | 修复 |
|------|------|------|------|
| 推断出 Latch | `proc` 输出 warning | `always_comb` 中未完整赋值 | 确保所有分支都有赋值 |
| 未连接输出端口 | `stat` 显示输出为 0 | 未使用的输出未连接 | 添加 `assign` 或确认故意悬空 |
| 黑盒警告 | `hierarchy` 警告 | 缺少子模块源文件 | 补充子模块 RTL 或设置 `-blackbox` |
| 组合逻辑环路 | `opt` 报错 | 输出反馈到输入 | 添加寄存器打破环路 |

#### 7.5.4 SDC 时序约束规范

##### SDC 文件结构化模板

```tcl
# =============================================================================
# constraints.sdc — 时序约束文件
# =============================================================================

# ── 参数定义区（便于跨项目复用）──
set CLK_NAME    clk
set CLK_PERIOD  5.0          ;# ns（可配置）
set CLK_PORT    [get_ports $CLK_NAME]

# ── 时钟定义 ──
create_clock -name $CLK_NAME -period $CLK_PERIOD $CLK_PORT

# ── 时钟不确定性（裕量）──
set_clock_uncertainty -setup 0.1 [get_clocks $CLK_NAME]
set_clock_uncertainty -hold  0.05 [get_clocks $CLK_NAME]
set_clock_transition         0.1 [get_clocks $CLK_NAME]

# ── 输入延迟（外部芯片 → 本模块）──
set_input_delay  -clock $CLK_NAME -max 1.0 [all_inputs]
set_input_delay  -clock $CLK_NAME -min 0.5 [all_inputs]

# ── 输出延迟（本模块 → 外部芯片）──
set_output_delay -clock $CLK_NAME -max 1.0 [all_outputs]
set_output_delay -clock $CLK_NAME -min 0.5 [all_outputs]

# ── 异步复位处理（作为 false path）──
set_false_path -from [get_ports rst_n]
set_false_path -to   [get_ports rst_n]

# ── 异步握手接口（CDC 边界）──
set_false_path -from [get_ports async_*]
set_false_path -to   [get_ports async_*]
```

**约束参数选择指南**：

| 参数 | 推荐值 | 调整原则 |
|------|-------|---------|
| `CLK_PERIOD` | 5ns (200MHz) | 根据目标工艺和频率需求调整 |
| `clock_uncertainty -setup` | period × 2% | 覆盖 skew + jitter，先进工艺取 5% |
| `clock_uncertainty -hold` | period × 1% | 通常为 setup 裕量的 50% |
| `clock_transition` | 0.1ns | 技术库默认值的 2 倍 |
| `input_delay` | period × 20% | 根据外部芯片输出延迟估算 |
| `output_delay` | period × 20% | 根据外部芯片输入建立时间估算 |

##### 多时钟域约束

```tcl
# ── 多时钟定义 ──
create_clock -name clk_core  -period 5.0 [get_ports clk_core]
create_clock -name clk_mem   -period 3.0 [get_ports clk_mem]

# ── 异步时钟组（独占分析）──
set_clock_groups -asynchronous \
  -group [get_clocks clk_core] \
  -group [get_clocks clk_mem]

# ── 跨时钟域路径约束（双触发器同步器后的边界）──
# 经过同步器后的路径视为 false path
set_false_path -from [get_pins sync_reg*/Q] -to [get_pins sync_reg*/D]
```

#### 7.5.5 OpenSTA 时序分析

##### STA 分析脚本

```tcl
# sta.tcl — OpenSTA 静态时序分析脚本
# 读取网表和库
read_liberty $::env(LIBERTY_FILE)
read_verilog build/dut_syn.v
link_design dut_top

# 读取 SDC 约束
read_sdc constraints/constraints.sdc

# 建立时间检查
report_checks -path_delay max -slack_lesser_than 0.0

# 保持时间检查
report_checks -path_delay min -slack_lesser_than 0.0

# 时序总览
report_tns     ;# 总负裕量
report_wns     ;# 最差负裕量

# 最差路径报告（Top 10）
report_checks -path_delay max -slack_lesser_than 0.1 -group_count 10

# 时钟偏移报告
report_clock_skew

# 退出
exit
```

##### 时序质量验收标准

| 指标 | 通过标准 | 说明 |
|------|---------|------|
| WNS（最大负裕量）| ≥ 0ns | 最差路径必须满足时序 |
| TNS（总负裕量）| = 0ns | 不允许任何时序违例 |
| Setup slack | ≥ 0ns（所有路径）| 建立时间必须满足 |
| Hold slack | ≥ 0ns（所有路径）| 保持时间必须满足 |
| 时钟 skew | < 时钟周期 × 5% | 偏移过大需优化时钟树 |

##### 时序违例诊断流程

```
Step 1: 获取违例路径报告 → report_checks -slack_lesser_than 0.0
Step 2: 分析关键路径 → 识别 longest path 和 highest fanout
Step 3: 确定根因：
  - 组合逻辑过长 → 插入流水线寄存器
  - 高扇出 → 复制驱动或插入 buffer
  - 时钟偏移 → 优化时钟树
  - 约束过严 → 调整 input/output delay
Step 4: 修复后重新综合 → 重新 STA 验证
Step 5: 记录修复过程 → 写入 design_notes
```

#### 7.5.6 CDC 跨时钟域检查

##### CDC 问题分类

| 类别 | 描述 | 解决方案 | 检查方法 |
|------|------|---------|---------|
| **单 bit 电平信号** | 慢→快或快→慢时钟域的单 bit 控制信号 | 双触发器同步器 | 人工审查 + `set_false_path` |
| **多 bit 数据总线** | 跨时钟域的多位数据 | 异步 FIFO / 握手协议 | 人工审查 |
| **脉冲信号** | 跨时钟域的单周期脉冲 | 脉冲同步器 | 人工审查 |
| **复位释放** | 异步复位释放的亚稳态风险 | 复位同步器 | `set_false_path` |

##### CDC 约束模板

```tcl
# ── 识别所有时钟域 ──
# Step 1: 列出所有时钟
# create_clock -name clk_A -period X ...
# create_clock -name clk_B -period Y ...

# Step 2: 声明异步时钟组
set_clock_groups -asynchronous \
  -group [get_clocks clk_A] \
  -group [get_clocks clk_B]

# Step 3: 对同步器输出应用 false path
# 双触发器同步器模板：
# always_ff @(posedge clk_B) begin
#   sync_r1 <= async_signal;  ← 第一级（false path source）
#   sync_r2 <= sync_r1;       ← 第二级（输出，同步后信号）
# end
set_false_path -from [get_pins sync_r1_reg/Q] -to [get_pins sync_r2_reg/D]
```

##### CDC 人工检查清单

| 检查项 | 描述 | 检查结果 |
|--------|------|---------|
| 所有跨时钟域信号是否有同步器 | 每个跨域信号链必须经过 2+ FF | □ |
| 同步器命名是否规范 | 信号名包含 `sync_` 前缀 | □ |
| 是否使用 `set_clock_groups` | 所有异步时钟对已声明 | □ |
| 同步器后路径是否设置 false path | 同步器输出端已约束 | □ |
| 异步 FIFO 是否正确使用 Gray 码 | 读写指针按 Gray 码传递 | □ |
| 复位是否跨时钟域 | 如有，需在每个时钟域独立同步 | □ |

#### 7.5.7 完整检查工作流（集成脚本）

```bash
#!/bin/bash
# check_all.sh — 完整设计检查流程
PROJECT_ROOT="/mnt/d/workspace/mixed_precision_dot_product"
RTL_DIR="$PROJECT_ROOT/rtl"
TB_DIR="$PROJECT_ROOT/tb"
BUILD_DIR="$PROJECT_ROOT/build"
SDC_FILE="$PROJECT_ROOT/constraints/constraints.sdc"

mkdir -p "$BUILD_DIR"

# ── Step 1: Verible Lint ──
echo "=== [1/4] Verible Lint ==="
verible-verilog-lint --ruleset=all "$RTL_DIR"/*.v 2>&1 | tee "$BUILD_DIR/lint_report.txt"

# ── Step 2: Icarus Verilog 仿真 ──
echo "=== [2/4] Simulation ==="
cd "$TB_DIR"
iverilog -g2012 -o "$BUILD_DIR/simv" \
  "$RTL_DIR"/*.v \
  tb_dot_product_pipeline.v
vvp "$BUILD_DIR/simv" | tee "$BUILD_DIR/sim_output.txt"

# ── Step 3: Yosys 综合 ──
echo "=== [3/4] Yosys Synthesis ==="
yosys -p "
  read_verilog -sv $RTL_DIR/params.vh;
  read_verilog $RTL_DIR/*.v;
  hierarchy -check -top dot_product_pipeline;
  proc; opt; fsm; opt;
  techmap; opt;
  stat -width;
  write_verilog -noattr $BUILD_DIR/dut_syn.v
" 2>&1 | tee "$BUILD_DIR/syn_report.txt"

# ── Step 4: OpenSTA 时序分析 ──
echo "=== [4/4] OpenSTA Timing ==="
if command -v sta &> /dev/null; then
  sta -no_splash -exit build/sta_report.txt <<EOF
read_liberty \$::env(LIBERTY_FILE)
read_verilog $BUILD_DIR/dut_syn.v
link_design dot_product_pipeline
read_sdc $SDC_FILE
report_checks -path_delay max -slack_lesser_than 0.0
report_tns
report_wns
exit
EOF
else
  echo "[WARNING] OpenSTA not installed. Run: apt install sta"
fi

# ── 汇总 ──
echo "=== Design Check Complete ==="
echo "Reports: $BUILD_DIR/lint_report.txt"
echo "          $BUILD_DIR/syn_report.txt"
echo "          $BUILD_DIR/sim_output.txt"
echo "          $BUILD_DIR/sta_report.txt"
```

#### 7.5.8 设计签核检查清单

进入物理设计前必须通过的检查项：

| 阶段 | 检查项 | 通过标准 | 工具 |
|------|--------|---------|------|
| Lint | 语法/风格 | 0 Error, 可控 Warning | Verible |
| 仿真 | 功能正确性 | pass_count = total, fail_count = 0 | Icarus / Verilator |
| 综合 | 可综合 | 无 Latch / 黑盒 / 环路 | Yosys |
| STA | 时序收敛 | WNS ≥ 0, TNS = 0 | OpenSTA |
| CDC | 跨时钟域 | 所有异步信号已同步，约束完整 | 人工 + SDC |

#### 7.5.9 Verible Lint 实战分类统计

以下数据来自 `dot_product_pipeline` 项目 7 个 RTL 文件的 Verible 全规则集检查结果（381 条警告）：

| 规则 | 数量 | 严重级别 | 根因 |
|------|------|---------|------|
| `port-name-suffix` | 99 | Style | 端口未遵循 `_i/_o` 命名后缀 |
| `line-length` | 95 | Style | 行宽超过 100 字符 |
| `explicit-parameter-storage-type` | 80 | Style | `parameter` 未显式声明存储类型 |
| `explicit-begin` | 39 | Style | `if/for` 后缺少显式 `begin/end` |
| `unpacked-dimensions-range-ordering` | 26 | Style | 数组维度声明顺序 `[0:N-1]` → 应为 `[N]` |
| `generate-constructs` (legacy) | 18 | Style | 使用了非 genvar 的旧式 generate |
| `instance-shadowing` | 10 | Style | 实例名与外层同名 |
| `always-comb` | 9 | Style | `always @*` → 应为 `always_comb` |
| `legacy-genvar-declaration` | 9 | Style | `genvar` 在 generate 块外声明 |
| `legacy-generate-region` | 7 | Style | 遗留 generate region 写法 |
| `case-missing-default` | 2 | Warning | case 缺少 default 分支 |
| 其他 | 7 | Style | EOF、trailing spaces 等 |

##### 按修复优先级分类

| 优先级 | 规则 | 数量 | 理由 |
|--------|------|------|------|
| **P0（立即）** | `case-missing-default` | 2 | 潜在推断 latch 风险 |
| **P1（尽快）** | `always-comb` | 9 | 仿真-综合不一致风险 |
| | `instance-shadowing` | 10 | 层次路径混淆 |
| **P2（计划）** | `generate-constructs` | 18 | 旧语法可能不被后续工具支持 |
| | `packed-dimensions-range-ordering` | 26 | 编码规范对齐 |
| **P3（可选）** | `port-name-suffix` | 99 | 仅影响风格一致性 |
| | `line-length` | 95 | 不影响功能 |
| | `explicit-parameter-storage-type` | 80 | 不影响功能 |
| | `explicit-begin` | 39 | 不影响功能 |

##### Lint 通过标准

- **硬标准**：P0 类问题 = 0；P1 类问题 < 原始数量的 30%
- **软标准**：P2 类问题可纳入技术债跟踪，逐版本收敛
- **豁免标准**：P3 类问题在团队风格规范明确前可保留

#### 7.5.10 Yosys 综合限制与 WSL 环境适配

##### WSL 环境内存限制

在 Windows WSL 环境中运行 Yosys 时，复杂设计的 RTLIL 展开可能因内存不足而卡死或崩溃：

- **现象**：Yosys 在 `read_verilog` / `hierarchy` 阶段超时（60s+），WSL pty 崩溃（`灾难性故障 E_UNEXPECTED`）
- **根因**：WSL 默认使用一半物理内存，大型 always 组合块生成的 RTLIL 网表对象数超标
- **影响阈值**：以 s2_multiplier_array 为例 — 32 通道 × 288 atom × 多模式展开 ≈ 数百万逻辑对象

##### 解决方案矩阵

| 策略 | 适用场景 | 操作 |
|------|---------|------|
| **分模块综合** | 子模块可独立综合 | 按 leaf → branch → top 顺序逐级综合 |
| **WSL 内存扩容** | 物理内存 ≥ 32GB | 创建 `%UserProfile%\.wslconfig`，设置 `memory=24GB` |
| **输出重定向** | 抑制终端 I/O 延迟 | `yosys ... > out.txt 2>&1`，将 stderr warnings 重定向 |
| **timeout 保护** | 防止终端卡死 | `timeout 120 yosys ...` |
| **Yosys -Q 模式** | 减少输出开销 | 添加 `-Q` 参数抑制 banner 和冗余日志 |
| **本地 Linux** | 确保资源充足 | 使用物理 Linux 或云 VM（≥16GB RAM） |

##### WSL Yosys 稳定运行命令模板

```bash
# 推荐：输出到文件 + timeout 保护 + 抑制 stderr
timeout 180 yosys -Q -p "
  read_verilog -sv params.vh rtl/*.v;
  hierarchy -check -top top_module;
  proc; opt;
  stat -width;
  write_verilog build/dut_syn.v
" > build/syn_full.log 2>&1
```

##### 工具安装注意事项（WSL）

| 工具 | 安装方式 | 注意事项 |
|------|---------|---------|
| Yosys | `apt-get install yosys` | 版本可能较旧（Ubuntu 22.04 = 0.9）；手动编译可获取最新版 |
| Verible | GitHub Releases 下载预编译二进制 | 不通过 apt 安装；解压后复制到 `/usr/local/bin` |
| OpenSTA | AppImage 或源码编译 | SWIG >= 4.x 需修改 CMakeLists.txt 移除版本约束 |
| Icarus | `apt-get install iverilog` | 安装简单，无特殊版本需求 |

#### 7.5.11 变界 for 循环可综合性修复

##### 问题描述

Yosys（以及大多数综合工具）要求 `for` 循环的边界必须为编译期常量。使用变量作为边界的循环会导致综合错误：

```
"2nd expression of procedural for-loop is not constant"
"Right hand side of 1st expression of procedural for-loop is not constant"
```

此限制源自综合工具需要将 for 循环**完全展开**为硬件电路，因此必须预知迭代次数。

##### 修复模式

**修复前（不可综合）**：
```verilog
// active 是运行时变量 → 循环边界不固定
for (ch = 0; ch < active; ch = ch + 1) begin
    ext_mant_a[EXT_MANT_W*ch +: EXT_MANT_W] = ...;
end
```

**修复后（可综合）**：
```verilog
// 定义编译期常量作为最大边界
localparam MAX_PARALLEL = 32;

// 使用常量边界 → 工具在编译期确定迭代次数
for (ch = 0; ch < MAX_PARALLEL; ch = ch + 1) begin
    if (ch < active) begin  // 运行时条件：仅活跃通道执行
        ext_mant_a[EXT_MANT_W*ch +: EXT_MANT_W] = ...;
    end
end
```

##### 本项目修复清单

| 文件 | 修复位置 | 变量边界 | 替换为 | 修复行数 |
|------|---------|---------|--------|---------|
| `s1_spv_format_expand.v` | channel 遍历 | `active` | `MAX_PARALLEL` + `if (ch < active)` | 1 |
| `s3_align_adder_normalize.v` | max_exponent 扫描 ×2 | `active_parallel` | `MAX_PARALLEL` + `if (ch < active_parallel)` | 2 |
| `s2_multiplier_array.v` | n_position 遍历 | `N_lane` | `MAX_N` + `if (n_position < N_lane)` | 1 |
| `s2_multiplier_array.v` | 高通道清零 | `K_LANES * N_lane` (start) | `0` + `if (ch >= K_LANES * N_lane)` | 1 |
| `s2_multiplier_array.v` | a_slice/b_slice 遍历 | `fn_a_slices`/`fn_b_slices` | `MAX_A_SLICES`/`MAX_B_SLICES` + 条件 | 4 |

##### 设计规则

> **所有综合目标 for 循环必须使用 `localparam` 常量作为边界**。运行时变量差异通过循环体内的 `if` 条件分支处理。新增常量定义统一放置在模块参数声明区，以 `MAX_` 前缀命名以便识别。

#### 7.5.12 综合警告诊断：范围越界

##### 警告特征

```
Warning: Range select [694:693] out of bounds on signal `\ext_mant_a_unpacked':
Setting all 2 result bits to undef.
```

##### 诊断三步法

**Step 1: 定位**。识别警告涉及的信号和越界偏移量：
- 信号名：`ext_mant_a_unpacked`
- 越界范围：`[694:693]`
- 信号声明位宽：`[EXT_MANT_W * MAX_PARALLEL - 1:0]` = `[351:0]`

**Step 2: 分析**。追踪越界访问的生成逻辑：
```verilog
// NVFP4_FP16 模式下，slot=15 时的展开偏移
ext_mant_a_unpacked[EXT_MANT_W*(4*slot+3) +: 2]  // → [694:693]
// EXT_MANT_W=11, slot=15 → 11*(60+3)+1 = 694
```
根因：NVFP4 展开率 4×（每个物理槽位包含 4 个逻辑元素），但 `ext_mant_a_unpacked` 的位宽仅按 `物理槽位数 × 尾数宽` 分配，未考虑最大展开倍数。

**Step 3: 修复**。重新计算所需位宽：
```verilog
// 修复前
wire [EXT_MANT_W * MAX_PARALLEL - 1:0] ext_mant_a_unpacked; // 352 bits

// 修复后：考虑最大展开率
localparam MAX_UNPACK_RATIO = 4;  // NVFP4 最多 4 个元素/槽位
wire [EXT_MANT_W * MAX_PARALLEL * MAX_UNPACK_RATIO / 2 - 1:0]
     ext_mant_a_unpacked;          // 704 bits
```

##### 通用诊断原则

| 警告类型 | 诊断方法 | 修复策略 |
|---------|---------|---------|
| range select out of bounds | 对比信号声明位宽与访问偏移 | 扩容信号位宽或限制访问范围 |
| inferred latch | 检查 case/if 完整性 | 补全 else/default 分支 |
| multi-driver | 查 grep `信号名` 的 assign/always 源 | 合并到单一 always 块 |
| blackbox | `hierarchy -check` 未解析 | 补充子模块源文件或 `-blackbox` 声明 |

---

## Phase 8: AI 波形调试工作流

### 8.1 debug_waveform.py — `--watch` 万能入口

零依赖 VCD 分析工具。所有模式输出结构化 JSON。

| 用法 | 模式 | 用途 |
|-------|------|------|
| `--watch` | 自动发现快照 | 仿真结束时 dump 端口 + 内部信号全状态 |
| `--watch <信号> --time <ps>` | 定向快照 | 指定时刻特定信号值 |
| `--watch <信号> --time T1-T2` | 时间窗口 | 窗口内所有信号变化追踪 |
| `--watch <信号> --trigger <沿> -n N` | 触发序列 | 按触发沿筛选的时序追踪 |
| `--list-signals [--pattern <pat>]` | 信号发现 | 列出信号层级，可选筛选 |

### 8.2 AI 信号选择原则

- **由广到窄**：控制信号（valid/idle/state）与数据信号（result/中间值）同时入手
- **流水线追踪**：沿流水级边界选信号，逐级定位分叉点
- **`--list-signals --pattern`**：发现 FSM（state/fsm）、算术中间值（sum/product/accum）、异常标志（overflow/underflow/stall）
- **时间窗口**：以故障时刻为终点，前推 `2~3 × 流水级数 × 时钟周期`

### 8.3 四阶段渐进调试

```
阶段 1 — 定位：--list-signals [--pattern <关键词>]
阶段 2 — 广角：--watch / --watch --time <Tps>
阶段 3 — 聚焦：--watch <信号> --trigger <沿> -n N / --time T1-T2
阶段 4 — 深入：--watch <子模块信号> --time <收窄窗口>
```

### 8.4 信号名解析

简写名如 `result`、`state_q` 自动匹配完整 VCD 路径（后缀模糊匹配）。多候选时优先变化最多的信号（最活跃 = 最可能是目标）。

### 8.5 JSON 输出格式

```json
{
  "time_ps": 95000,
  "time_ns": 95.0,
  "signals": {
    "result": {"bin": "...", "hex": "0x..."},
    "mode":   {"bin": "01", "hex": "0x1"}
  }
}
```
