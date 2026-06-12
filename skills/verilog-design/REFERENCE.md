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

| 维度     | 硬件电路                        | 软件程序               |
| -------- | ------------------------------- | ---------------------- |
| 执行方式 | 所有逻辑**同时并行**工作        | 指令**逐条串行**执行   |
| 时间单位 | 时钟周期 CLK、建立/保持时间     | CPU 指令周期           |
| 存储     | 寄存器、SRAM、DRAM、ROM、锁存器 | 变量、数组、堆/栈      |
| 控制流   | 状态机 FSM、流水线握手          | 函数调用、循环、分支   |
| 数据     | bit 位宽、总线、码制            | 字节、类型、对象       |
| 正确性   | 时序收敛、亚稳态、毛刺          | 逻辑正确、内存安全     |
| 优化目标 | Fmax、面积、功耗、延迟          | 时间复杂度、空间复杂度 |

### 0.3 硬件设计四维权衡

任何设计决策都是四个维度的折中：

- **速度（Fmax）**：最高工作频率。加法器链延迟 > 流水级延迟 → 插寄存器拆分
- **面积（Area）**：门数、FF 数、RAM 块数。并行阵列面积大，时分复用面积小
- **功耗（Power）**：动态功耗（∝ 翻转率 × 电容 × V² × f）+ 静态功耗（漏电流）
- **延迟（Latency）**：输入到输出的时钟周期数。流水线加延迟但提吞吐

**不可能三角**：速度、面积、功耗不可兼得。任意两个优化必然牺牲第三个。

### 0.4 从软件思维到硬件思维的转换表

| 软件概念           | 硬件对应                                     |
| ------------------ | -------------------------------------------- |
| `for`/`while` 循环 | 状态机多周期迭代 / 流水线展开 / 并行硬件阵列 |
| `if`/`else` 条件   | 多路选择器 MUX、组合逻辑门                   |
| `int x = 5;` 变量  | 寄存器 `reg [31:0] x_q`                      |
| 数组 `a[100]`      | 寄存器堆 / SRAM / 多路选择器阵列             |
| 函数调用           | 模块实例化、组合逻辑块                       |
| 递归               | 硬件不支持。拆为迭代状态机                   |
| `malloc`/`free`    | 硬件无动态分配。资源在综合时确定             |
| `sleep(ms)`        | 计数器 + 使能信号。禁用绝对延时 `#delay`     |
| 线程/并发          | 并行硬件模块、多时钟域                       |
| try/catch 异常     | 溢出标志位、valid 信号、FIFO 满/空           |
| 内存地址/指针      | 总线地址译码、片选 CS 信号                   |

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

#### 需求矩阵分析（通用流程）

枚举所有工作模式，按「并行度 × 位宽」构建需求矩阵，识别各子系统的峰值需求与闲置区间：

| 模式             | 并行度 | 数据位宽 | 总资源需求 |
| ---------------- | ------ | -------- | ---------- |
| 模式 A（高精度） | N_A    | W_A      | N_A × W_A  |
| 模式 B（中精度） | N_B    | W_B      | N_B × W_B  |
| 模式 C（低精度） | N_C    | W_C      | N_C × W_C  |

**关键洞察**：若按 max(N) × max(W) 声明物理资源，闲置率可达 40-65%。物理资源应定义为各模式的**合理交集**而非笛卡尔积。

#### 设计模式一：运算器阵列复用

**场景**：多模式运算需求不同，高精度模式需要完整运算器，低精度模式仅需子集。

**方法**：按各模式用量的**最大值**实例化每种运算器，通过输入切片和索引偏移实现跨模式共享。

```
实例化策略（逐运算类型求最大值）:
  Op_Type_A × N:  max(模式A=N_A, 模式B=N_B, ...)  ← 覆盖所有模式
  Op_Type_B × N:  max(模式A=N_A', 模式B=0, ...)   ← 仅高精度需要
```

**技术要点**：

| 要点             | 说明                                                           |
| ---------------- | -------------------------------------------------------------- |
| **切片感知模式** | 高精度模式提取完整数据范围；低精度模式仅提取有效低位，高位填空 |
| **对等信号复用** | 语义对等的子信号共享同一组运算器，通过索引偏置区分来源         |
| **旁路替代**     | 极低位宽（≤2-bit）运算可用位移加法替代完整乘法器实例化         |

#### 设计模式二：寄存器位宽复用（位拆分存储）

**场景**：高精度模式通道少但位宽大，低精度模式通道多但位宽小。按 max(N) × max(W) 声明寄存器导致大量高位闲置。

**方法**：物理寄存器槽位按高精度模式的并行度 N_high 定义。低精度模式下，将多个窄位宽数据打包存入同一物理槽位。

```
物理寄存器结构:
  PHYS_SLOTS  = N_high    (固定槽位数，等于高精度模式通道数)
  PHYS_WIDTH  = W_high    (每槽位宽)
  PHYS_REG_W  = N_high × W_high

映射策略:
  高精度模式: slot[i][W_high-1:0]  ← ch[i] 数据           → 1:1 直接映射
  低精度模式: slot[i][W_low-1:0]  ← ch[2i] 数据           → 2:1 位拆分
              slot[i][2W_low-1:W_low] ← ch[2i+1] 数据      → 两个数据/槽位
```

**关键设计模式**：

| 阶段         | 操作                           | 说明                               |
| ------------ | ------------------------------ | ---------------------------------- |
| **内部处理** | 全格式展开为 `max(N) × max(W)` | 方便逐通道遍历，无需位操作         |
| **打包出口** | 按模式压缩为 `PHYS_REG_W`      | 模块间传递紧凑格式，节省跨级寄存器 |
| **解包入口** | 恢复为内部全格式               | 下游模块按需解包，保持处理逻辑统一 |

#### 方法论原则

| #   | 原则                       | 说明                                                |
| --- | -------------------------- | --------------------------------------------------- |
| 1   | **先分析再设计**           | 枚举所有模式的并行度 × 位宽需求矩阵，识别峰值与闲置 |
| 2   | **物理资源定上限**         | 寄存器/运算器按合理交集定义上限，非最大值的笛卡尔积 |
| 3   | **打包在出口，解包在入口** | 接口传紧凑格式省寄存器，内部展开全格式便处理        |
| 4   | **参数化声明**             | `parameter/localparam` 定义物理规格，支持跨配置裁剪 |
| 5   | **旁路优于虚耗**           | 简单运算（位移/加法）可替代时，不做完整运算器实例化 |
| 6   | **对等复用优先**           | 两信号位宽与计算模式对等时，索引偏移复用同一组硬件  |

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

10. **禁止恒真/恒假条件**：条件表达式必须依赖运行时信号值变化，不允许写出在综合期已确定为恒真或恒假的判断语句。

    **常见违规模式：**

- 字面恒值条件：`if (1'b1)`、`if (0)`、`if (1)`
- 参数/常量恒真条件：`if (WIDTH > 0)`（WIDTH 为 parameter，编译期已知结果）
- 自比较恒真条件：`if (signal == signal)`、`if (a <= a)`
- 常量范围恒真：`if (index >= 0)`（index 为无符号，恒真）

```verilog
// 错误：WIDTH 为 parameter，编译期已知 > 0，条件恒真
parameter WIDTH = 16;
if (WIDTH > 0)
    data_out = data_in;

// 错误：自比较恒真
if (counter == counter)
    valid = 1'b1;

// 正确：条件依赖运行时信号
if (enable)
    data_out = data_in;
if (counter == threshold)
    valid = 1'b1;
```

> **审查要点**：写入每条 `if`/`case` 条件前，静态审视其是否仅依赖编译期常量。若条件变量全部为 `parameter`/`localparam`/字面量，则必须删除该条件分支，直接保留有效代码路径。

11. **`for` 循环终止条件必须为编译期常量**：`for` 循环的终止条件必须是 `parameter`、`localparam` 或整数字面量，确保综合工具可静态展开为确定的硬件结构。禁止使用 `reg`/`wire` 等运行时信号作为终止条件。

```verilog
// 错误：终止条件为运行时信号 → 综合工具无法静态展开
reg [3:0] count;
always @(*) begin
    sum = 0;
    for (i = 0; i < count; i = i + 1)  // count 为 reg，综合不可预测
        sum = sum + data[i];
end

// 正确：终止条件为常量 → 综合工具确定展开次数
localparam NUM_ELEMENTS = 8;
always @(*) begin
    sum = 0;
    for (i = 0; i < NUM_ELEMENTS; i = i + 1)
        sum = sum + data[i];
end
```

> **设计意图**：RTL 中 `for` 循环的本质是**硬件展开描述**，不是软件迭代。展开次数必须在综合期确定，才能生成确定的加法器链/MUX 阵列等硬件结构。若需要运行时可变迭代次数，应设计为状态机（FSM）逐周期处理。

12. **禁止同一 `always` 块内对同一信号多次赋值**（组合逻辑默认赋初值除外）。在组合逻辑 `always @(*)` 块中，允许在块顶部用默认赋值作为"兜底"，然后在后续 `if`/`case` 分支中覆盖。时序逻辑 `always @(posedge clk)` 块中，每个信号只能赋值一次。

    **为什么这样要求：**

- 多次赋值时，只有**最后一次**生效（Verilog 语义），容易引入隐式优先级，导致综合结果与设计意图不一致
- 时序逻辑中多次赋值可能被综合为隐式优先级 MUX 链，面积膨胀且时序恶化
- 增加代码可读性和可维护性，每个信号的赋值逻辑一目了然

```verilog
// ==================== 组合逻辑 ====================

// 正确：默认赋初值 + 分支覆盖（允许的唯一多次赋值模式）
always @(*) begin
    result = {WIDTH{1'b0}};   // 第一次：默认赋初值（兜底）
    busy     = 1'b0;
    if (start) begin
        result = data_in;      // 第二次：分支覆盖（非默认赋值，仅此位置）
        busy     = 1'b1;
    end
end

// 错误：同一信号多处非默认赋值 → 隐式优先级，最后一个写入生效
always @(*) begin
    result = data_a;
    if (sel_a)
        result = data_a;       // 冗余赋值
    if (sel_b)
        result = data_b;       // sel_a 和 sel_b 同时有效时，此处生效（隐式优先级）
    if (sel_c)
        result = data_c;       // 此处最优先，设计意图不清晰
end
// 应改写为 casez 或显式优先级编码

// ==================== 时序逻辑 ====================

// 正确：每个信号只赋值一次
always @(posedge clk) begin
    if (rst) begin
        state_q <= IDLE;
    end else begin
        state_q <= next_state;
    end
end

// 错误：时序逻辑中多次赋值 → 只有最后一次生效，综合出隐式优先级
always @(posedge clk) begin
    state_q <= IDLE;
    if (en1)
        state_q <= S1;         // 覆盖 IDLE
    if (en2)
        state_q <= S2;         // 覆盖 S1，en1=en2=1 时 state_q=S2
end
// 应改写为 if-else 显式优先级
```

> **审查要点**：在 `always` 块中搜索同一信号名出现次数。组合逻辑块中，允许模式为「1 次默认赋初值 + N 次分支覆盖」。时序逻辑块中，同一信号必须只出现 1 次赋值。违反此规则的代码应重构为 `case`/`casez` 或显式 `if-else if` 链。

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

| 运算         | 结果位宽          | 原因         |
| ------------ | ----------------- | ------------ |
| 加法 `a + b` | `max(Wa, Wb) + 1` | 进位位       |
| 乘法 `a × b` | `Wa + Wb`         | 最大乘积位宽 |
| 减法 `a - b` | `max(Wa, Wb) + 1` | 符号/借位位  |

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

| exp[4:0] | mant[9:0] | 含义                                    |
| -------- | --------- | --------------------------------------- |
| 0        | 0         | 零（有符号 ±0）                         |
| 0        | ≠0        | 次正规数                                |
| 1~30     | 任意      | 规格化数 = (-1)^s × 1.mant × 2^(exp-15) |
| 31       | 0         | 无穷大 ±∞                               |
| 31       | ≠0        | NaN                                     |

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

| 类型             | 说明                                           | 示例                                    |
| ---------------- | ---------------------------------------------- | --------------------------------------- |
| **标准测试向量** | 算法/协议标准中给出的官方测试用例              | SM3 的 "abc" 测试向量、IEEE 754 特殊值  |
| **边界长度**     | 空消息、单字节、最大块长度、非整数块           | SHA-256 的空消息 hash、块边界对齐       |
| **多块链式**     | 连续两笔以上数据，验证流水线状态保持和链式迭代 | 多块 hash 链式、连续浮点运算            |
| **边界值**       | 最大值、最小值、零、溢出/下溢                  | FP16 的 INF/NaN、有符号 INT16 的 -32768 |
| **随机测试**     | 大量随机输入交叉验证（DUT vs 参考模型）        | `$urandom(seed)` 生成千级测试           |

### 4.5 调试打印方法学

自检测试平台（Self-Checking Testbench）不仅依赖波形分析，更需要结构化的调试打印体系。以下方法学适用于任意 RTL 模块的测试验证。

#### 4.5.1 核心组件

每个测试模块应包含以下标准组件：

| 组件                        | 类型       | 说明                                     |
| --------------------------- | ---------- | ---------------------------------------- |
| `pass_count` / `fail_count` | `integer`  | 全局通过/失败计数器，仿真结束时输出汇总  |
| `cycle` (可选)              | `integer`  | 周期计数器，用于调试打印的时间戳标注     |
| `wait_timeout`              | `integer`  | 超时等待计数器，防止仿真死锁             |
| `check_*` task(s)           | `task`     | 结果验证任务，自动比对期望值与实际输出   |
| `fill_*` function(s)        | `function` | 输入填充函数，快速构造不同格式的测试向量 |
| `init_*` / `set_*` task(s)  | `task`     | 初始化/设置任务，统一管理信号赋值        |

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
$display("=== TEST <N>: <操作模式> <输入描述> -> <期望输出> ===");

// ── 子测试分区标题 ──
$display("--- <分区名>: <描述> ---");
```

**命名规范**：

- 顶层测试标题：`=== TEST <N>: <模式> <输入描述> -> <期望输出> ===`
- 分区标题：`--- <分区名>: <描述> ---`
- 子测试标题：`<缩写>: <描述>`（如 `D1: <模式> N=<N>`、`RAND <模式> seed=<seed>`）

#### 4.5.3 结果验证 Task 模式

##### 模式 A：通用比对 Task（端到端验证）

适用于输出可直接比对期望值的场景：

```verilog
task check_result;
    input [EXPECTED_W-1:0] expected;
    input [255:0] test_name;
    begin
        if (o_result[EXPECTED_W-1:0] === expected) begin
            pass_count = pass_count + 1;
            $display("[PASS] %0s: got=0x%08X, expected=0x%08X", test_name, o_result, expected);
        end else begin
            fail_count = fail_count + 1;
            $display("[FAIL] %0s: got=0x%08X, expected=0x%08X", test_name, o_result, expected);
        end
    end
endtask
```

**关键设计点**：

- 同时打印实际值和期望值的十六进制表示，方便直接比对 bit pattern
- `[PASS]`/`[FAIL]` 前缀便于日志 grep 筛选
- `EXPECTED_W` 声明为 `localparam`，按模块输出位宽设置

##### 模式 B：Golden Model 比对 Task（中间级验证）

适用于需要软件参考模型计算期望值的场景：

```verilog
task check_channel;
    input [CH_IDX_W-1:0] ch_idx;
    input string test_name;
    reg [CH_DATA_W-1:0] golden_data;
    begin
        // 用 golden 函数计算期望值
        golden_data = golden_model(mode, input_a, input_b);
        // 逐字段比对
        if (channel_data[ch_idx*CH_DATA_W +: CH_DATA_W] === golden_data) begin
            pass_count = pass_count + 1;
        end else begin
            fail_count = fail_count + 1;
            $display("  [FAIL] %0s ch=%0d: got=%0d(golden=%0d)",
                     test_name, ch_idx,
                     channel_data[ch_idx*CH_DATA_W +: CH_DATA_W], golden_data);
        end
    end
endtask
```

**关键设计点**：

- golden（黄金参考）函数与 RTL 逻辑完全对齐，两者独立开发
- 失败时打印所有差异字段，便于快速定位根因
- channel 级粒度便于隔离故障通道

##### 模式 C：信号存在性检查

适用于仅需验证信号是否触发（非精确值）的场景：

```verilog
task check_non_zero;
    input [LANE_IDX_W-1:0] lane_n;
    input string test_name;
    begin
        if ($signed(lane_accum[ACCUM_W*lane_n +: ACCUM_W]) != 0 && lane_valid[lane_n] === 1'b1) begin
            pass_count = pass_count + 1;
            $display("  [PASS] %0s (lane%0d): accum=%0d", test_name, lane_n,
                     $signed(lane_accum[ACCUM_W*lane_n +: ACCUM_W]));
        end else begin
            fail_count = fail_count + 1;
            $display("  [FAIL] %0s (lane%0d): accum=%0d, valid=%b",
                     test_name, lane_n,
                     $signed(lane_accum[ACCUM_W*lane_n +: ACCUM_W]), lane_valid[lane_n]);
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

在开发初期，通过 `always @(negedge clk)` 加周期范围限制，密集打印关键内部信号：

```verilog
// ── 开发调试：前 N 个周期密集监控 ──
always @(negedge clk) begin
    if (cycle > 0 && cycle <= CYCLE_MONITOR_LIMIT) begin
        $display("DEBUG cycle=%0d: in_ready=%b in_valid=%b out_valid=%b",
                 cycle, in_ready, in_valid, out_valid);
        // 控制信号级联追踪：逐级打印流水线 valid 链
        $display("  pipe_valid[0]=%b pipe_valid[1]=%b pipe_valid[N-1]=%b",
                 u_submod[0].pipe_valid,
                 u_submod[1].pipe_valid,
                 u_submod[N-1].pipe_valid);
    end
end
```

**使用原则**：

- `CYCLE_MONITOR_LIMIT` 定义为 `localparam`，通常在 30-100 之间
- 仅在开发早期启用，正式验证时应注释或移除
- 通过分层打印组织信号：控制信号 → 数据信号 → 状态标志
- 使用 DUT 层级路径访问内部信号（`u_submod[0].pipeline_stage`）

##### 内联调试打印（定向测试中）

在定向测试 Task 内部直接插入调试打印：

```verilog
$display("    [<模块名>-debug] mode=0x%h ch0_data=%0d slot0_raw=%b",
         mode_code,
         channel_data[0 +: CH_DATA_W],
         slot_raw[0 +: SLOT_W]);
```

**命名约定**：`[<模块名>-debug]` 前缀，便于 grep 筛选和事后清理。

#### 4.5.6 随机测试打印规范

随机测试需要记录种子值以便复现：

```verilog
$display("  [PASS] RAND %0s seed=%0d (lane%0d): result=%0d",
         mode_name, seed, lane_n, $signed(lane_result));
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

#### 4.5.10 测试验证框架模板

##### 测试模块层级结构

一个完整的 RTL 模块验证体系应包含以下层次：

| 层级         | 测试目标                    | 验证方法                            | 推荐打印模式                 |
| ------------ | --------------------------- | ----------------------------------- | ---------------------------- |
| **端到端**   | 完整流水线全路径            | 定向 + 随机输入，DUT 输出 vs 期望值 | 模式 A（通用比对）+ 超时保护 |
| **中间级 1** | 流水线前级（格式解析/展开） | 随机输入，golden model 逐项比对     | 模式 B（Golden Model）       |
| **中间级 2** | 流水线中段（运算阵列）      | 随机输入，子字段黄金参考比对        | 模式 B                       |
| **中间级 3** | 流水线后级（累加/归一化）   | 定向 + 边界条件覆盖                 | 模式 A + C                   |
| **格式专项** | 特定数据格式编解码逻辑      | 枚举所有编码组合，逐项验证          | 模式 B                       |

##### 验证覆盖维度

| 维度         | 覆盖要求 | 说明                                  |
| ------------ | -------- | ------------------------------------- |
| **操作模式** | 100%     | 所有模式组合（高×高、高×低、低×低等） |
| **通道组合** | 主流值   | 最小/中值/最大并行度，含跨边界值      |
| **级联路径** | 已覆盖   | 级联输入/输出传播路径                 |
| **边界条件** | 全部     | subnormal、零值、溢出、最大/最小指数  |
| **随机种子** | 多组     | 每个模式的定向测试后附加随机回测      |

##### 打印日志量管理策略

| 阶段         | 打印级别 | 具体做法                                                         |
| ------------ | -------- | ---------------------------------------------------------------- |
| **开发期**   | 详细     | `[DBG]` 前缀 + `always @(negedge clk)` 条件监控，限制 cycle ≤ 50 |
| **验证期**   | 精简     | 仅 `[PASS]`/`[FAIL]` 打印，`[DBG]` 全部注释                      |
| **回归期**   | 聚合     | `[PASS]` 聚合为计数，仅 `[FAIL]` 详细打印                        |
| **定位技巧** | 筛选     | `grep FAIL build/sim_*.txt` 一键汇总所有失败项                   |

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
| ------ | ------------ | ---------- |
| 0      | `stage_0_X`  | `s0_X`     |
| 1      | `stage_1_X`  | `s1_X`     |
| N      | `stage_N_X`  | `sN_X`     |

- `sN_` = 第 N 级时序寄存器输出
- `i_` = 模块输入端口
- `o_` = 模块输出端口
- `_q` 后缀 = 弃用的旧寄存器（重构过渡）

#### 信号命名基本准则

| 准则               | 说明                                                                                                |
| ------------------ | --------------------------------------------------------------------------------------------------- |
| **禁止无意义短名** | 禁止单字母或 ≤3 字符且含义不明确的信号名，如 `tmp`、`arr`、`sig`                                    |
| **语义必须清晰**   | 信号名应准确反映功能和用途，如 `fifo_wr_en`（可读）                                                 |
| **循环变量例外**   | `for` 循环中的生成变量 `i`、`j`、`k` 允许单字母，但 loop 体内部信号仍须有语义名                     |
| **测试平台例外**   | 测试平台中的临时比对变量可接受简短名，但必须注释说明用途                                            |
| **避免缩写歧义**   | 通用缩写允许（`en`=enable, `addr`=address, `clk`=clock, `rst`=reset），自定义缩写须在文件头注释说明 |
| **名称长度**       | 推荐 8~40 字符。太短语义不足，太长影响波形阅读                                                      |

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

| 目标        | 命令（WSL 内）               | 用途                                   |
| ----------- | ---------------------------- | -------------------------------------- |
| `sim`       | `make sim`                   | 先编译 `.v` → `simv`，再运行 `vvp`     |
| `sim-clean` | `make sim-clean && make sim` | 清理 `simv` + `*.vcd` + 临时文件再仿真 |
| `clean`     | `make clean`                 | 删除整个 `sim/` 目录                   |
| `wave`      | `make wave`                  | 用 GTKWave 打开最新波形                |
| `syn`       | `make syn`                   | Yosys 综合                             |

> **为什么不把 `sim-clean` 放在 `sim` 的依赖里？**  
> 前置清理会**每次都重新编译**（增量编译失效），开发迭代中期频繁改少量代码时应避免。  
> 需要清理时显式执行 `make sim-clean && make sim`，或脚本中统一加清理。
>
> **哪些文件需要清理？**
>
> - `simv` — 编译的仿真可执行文件（iverilog 输出）
> - `*.vcd` / `*.lxt` / `*.lxt2` — 波形 dump 文件
> - `vvp.tmp` / `.vvp_tmp` — vvp 运行时生成的临时文件
> - `*.o` — 如果使用了 C 模型（PLI/VPI 扩展）

### 7.5 SDC/CDC 检查方法学

基于 Yosys + OpenSTA + Verible 工具链的系统化设计检查方法，覆盖 Lint（代码规范）、Synthesis（综合）、STA（静态时序分析）和 CDC（跨时钟域）四个维度。

#### 7.5.1 工具链概览

| 工具               | 用途                                                | 安装方式                            | 输出                     |
| ------------------ | --------------------------------------------------- | ----------------------------------- | ------------------------ |
| **Verible**        | Verilog/SystemVerilog Lint 检查，代码风格与语法规范 | 预编译二进制 `verible-verilog-lint` | Lint 报告（结构化文本）  |
| **Yosys**          | RTL 综合、逻辑优化、网表生成                        | `apt-get install yosys`             | 综合网表 + 面积/时序报告 |
| **OpenSTA**        | 静态时序分析（STA），SDC 约束验证                   | 源码编译 / AppImage                 | 时序违例报告、路径分析   |
| **Icarus Verilog** | 仿真验证                                            | `apt-get install iverilog`          | VCD 波形                 |

**工具版本要求**：

| 工具           | 最低版本  | 推荐版本   | 验证方式                         |
| -------------- | --------- | ---------- | -------------------------------- |
| Verible        | v0.0-3xxx | v0.0-4071+ | `verible-verilog-lint --version` |
| Yosys          | 0.9       | 0.27+      | `yosys --version`                |
| OpenSTA        | 2.2.0     | 2.2.0+     | `sta -version`                   |
| Icarus Verilog | 10.0      | 11.0+      | `iverilog -V`                    |

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

| 问题                             | Verible 规则                | 原因                 | 修复                             |
| -------------------------------- | --------------------------- | -------------------- | -------------------------------- |
| `generate` 块缺少 label          | `generate-label`            | 未命名的 generate 块 | 添加 `genvar` 及 `begin : label` |
| Tab 字符                         | `no-tabs`                   | 混用 Tab 和空格缩进  | 统一为空格缩进                   |
| 文件末尾无换行                   | `posix-eof`                 | POSIX 标准要求       | 文件末尾添加空行                 |
| `always @*` 应改为 `always_comb` | `always-comb`               | SV 最佳实践          | 替换为 `always_comb`             |
| 宏定义使用                       | `forbidden-macro`           | 宏滥用增加调试难度   | 改用 `localparam` / `function`   |
| 二进制常量位宽不足               | `undersized-binary-literal` | `'b1` 未指定位宽     | 改为 `1'b1`                      |

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

# 完整综合流程（SDC 约束通过命令行注入）
yosys -p "
  read_verilog -sv params.vh rtl/*.v;
  hierarchy -check -top <top_module>;
  proc; opt; fsm; opt;
  techmap; opt;
  abc -liberty \$LIBERTY;
  stat -width;
  write_verilog build/dut_syn.v
"
```

##### 综合质量检查清单

| 检查项           | Yosys 命令         | 通过标准              |
| ---------------- | ------------------ | --------------------- |
| 模块层次完整性   | `hierarchy -check` | 无未解析的模块引用    |
| Latch 检查       | `proc` 后查看警告  | 无 "found latch" 警告 |
| 组合逻辑环路检测 | `opt` 后检查       | 无组合环路            |
| 面积估算         | `stat`             | 面积在预期范围内      |
| 多驱动检查       | `check`            | 无多驱动信号          |

##### 常见综合问题

| 问题           | 现象                | 根因                       | 修复                              |
| -------------- | ------------------- | -------------------------- | --------------------------------- |
| 推断出 Latch   | `proc` 输出 warning | `always_comb` 中未完整赋值 | 确保所有分支都有赋值              |
| 未连接输出端口 | `stat` 显示输出为 0 | 未使用的输出未连接         | 添加 `assign` 或确认故意悬空      |
| 黑盒警告       | `hierarchy` 警告    | 缺少子模块源文件           | 补充子模块 RTL 或设置 `-blackbox` |
| 组合逻辑环路   | `opt` 报错          | 输出反馈到输入             | 添加寄存器打破环路                |

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

| 参数                       | 推荐值       | 调整原则                          |
| -------------------------- | ------------ | --------------------------------- |
| `CLK_PERIOD`               | 5ns (200MHz) | 根据目标工艺和频率需求调整        |
| `clock_uncertainty -setup` | period × 2%  | 覆盖 skew + jitter，先进工艺取 5% |
| `clock_uncertainty -hold`  | period × 1%  | 通常为 setup 裕量的 50%           |
| `clock_transition`         | 0.1ns        | 技术库默认值的 2 倍               |
| `input_delay`              | period × 20% | 根据外部芯片输出延迟估算          |
| `output_delay`             | period × 20% | 根据外部芯片输入建立时间估算      |

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

| 指标              | 通过标准          | 说明                 |
| ----------------- | ----------------- | -------------------- |
| WNS（最大负裕量） | ≥ 0ns             | 最差路径必须满足时序 |
| TNS（总负裕量）   | = 0ns             | 不允许任何时序违例   |
| Setup slack       | ≥ 0ns（所有路径） | 建立时间必须满足     |
| Hold slack        | ≥ 0ns（所有路径） | 保持时间必须满足     |
| 时钟 skew         | < 时钟周期 × 5%   | 偏移过大需优化时钟树 |

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

| 类别                | 描述                                | 解决方案             | 检查方法                    |
| ------------------- | ----------------------------------- | -------------------- | --------------------------- |
| **单 bit 电平信号** | 慢→快或快→慢时钟域的单 bit 控制信号 | 双触发器同步器       | 人工审查 + `set_false_path` |
| **多 bit 数据总线** | 跨时钟域的多位数据                  | 异步 FIFO / 握手协议 | 人工审查                    |
| **脉冲信号**        | 跨时钟域的单周期脉冲                | 脉冲同步器           | 人工审查                    |
| **复位释放**        | 异步复位释放的亚稳态风险            | 复位同步器           | `set_false_path`            |

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

| 检查项                          | 描述                         | 检查结果 |
| ------------------------------- | ---------------------------- | -------- |
| 所有跨时钟域信号是否有同步器    | 每个跨域信号链必须经过 2+ FF | □        |
| 同步器命名是否规范              | 信号名包含 `sync_` 前缀      | □        |
| 是否使用 `set_clock_groups`     | 所有异步时钟对已声明         | □        |
| 同步器后路径是否设置 false path | 同步器输出端已约束           | □        |
| 异步 FIFO 是否正确使用 Gray 码  | 读写指针按 Gray 码传递       | □        |
| 复位是否跨时钟域                | 如有，需在每个时钟域独立同步 | □        |

#### 7.5.7 完整检查工作流（集成脚本）

```bash
#!/bin/bash
# check_all.sh — 完整设计检查流程（通用模板，按项目修改路径）
PROJECT_ROOT="<project_root>"
RTL_DIR="$PROJECT_ROOT/rtl"
TB_DIR="$PROJECT_ROOT/tb"
BUILD_DIR="$PROJECT_ROOT/build"
SDC_FILE="$PROJECT_ROOT/constraints/constraints.sdc"

TOP_MODULE="<top_module>"
TB_TOP="<tb_top_module>"

mkdir -p "$BUILD_DIR"

# ── Step 1: Verible Lint ──
echo "=== [1/4] Verible Lint ==="
verible-verilog-lint --ruleset=all "$RTL_DIR"/*.v 2>&1 | tee "$BUILD_DIR/lint_report.txt"

# ── Step 2: Icarus Verilog 仿真 ──
echo "=== [2/4] Simulation ==="
cd "$TB_DIR"
iverilog -g2012 -o "$BUILD_DIR/simv" \
  "$RTL_DIR"/*.v \
  "$TB_DIR/$TB_TOP.v"
vvp "$BUILD_DIR/simv" | tee "$BUILD_DIR/sim_output.txt"

# ── Step 3: Yosys 综合 ──
echo "=== [3/4] Yosys Synthesis ==="
yosys -p "
  read_verilog -sv $RTL_DIR/params.vh 2>/dev/null;   # 可选参数文件
  read_verilog $RTL_DIR/*.v;
  hierarchy -check -top $TOP_MODULE;
  proc; opt; fsm; opt;
  techmap; opt;
  stat -width;
  write_verilog -noattr $BUILD_DIR/dut_syn.v
" 2>&1 | tee "$BUILD_DIR/syn_report.txt"

# ── Step 4: OpenSTA 时序分析 ──
echo "=== [4/4] OpenSTA Timing ==="
if command -v sta &> /dev/null; then
  sta -no_splash -exit <<EOF
read_liberty \$::env(LIBERTY_FILE)
read_verilog $BUILD_DIR/dut_syn.v
link_design $TOP_MODULE
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

| 阶段 | 检查项     | 通过标准                           | 工具               |
| ---- | ---------- | ---------------------------------- | ------------------ |
| Lint | 语法/风格  | 0 Error, 可控 Warning              | Verible            |
| 仿真 | 功能正确性 | pass_count = total, fail_count = 0 | Icarus / Verilator |
| 综合 | 可综合     | 无 Latch / 黑盒 / 环路             | Yosys              |
| STA  | 时序收敛   | WNS ≥ 0, TNS = 0                   | OpenSTA            |
| CDC  | 跨时钟域   | 所有异步信号已同步，约束完整       | 人工 + SDC         |

#### 7.5.9 Verible Lint 规则分类与修复优先级

Verible 全规则集检查会产生多种类型的警告，以下按严重级别分类：

| 规则类别          | 典型规则                                                                     | 严重级别      | 根因                                    |
| ----------------- | ---------------------------------------------------------------------------- | ------------- | --------------------------------------- |
| **Naming**        | `port-name-suffix`、`signal-name-style`                                      | Style         | 端口/信号名未遵循命名约定               |
| **Formatting**    | `line-length`、`explicit-begin`、`indentation`                               | Style         | 代码格式不符合规范                      |
| **Declaration**   | `explicit-parameter-storage-type`、`unpacked-dimensions-range-ordering`      | Style         | 声明未遵循最佳实践                      |
| **Legacy syntax** | `generate-constructs`、`legacy-genvar-declaration`、`legacy-generate-region` | Style         | 使用被 SystemVerilog 淘汰的旧语法       |
| **Semantic**      | `always-comb`、`instance-shadowing`                                          | Style/Warning | `always @*` → `always_comb`、实例名冲突 |
| **Correctness**   | `case-missing-default`、`port-width-mismatch`                                | Warning       | 潜在功能逻辑风险                        |

##### 按修复优先级分类

| 优先级         | 类别                       | 理由                              |
| -------------- | -------------------------- | --------------------------------- |
| **P0（立即）** | Correctness（0 Warning）   | 潜在推断 latch、功能错误风险      |
| **P1（尽快）** | Semantic（收敛至 ≤30%）    | 仿真-综合不一致风险、层次路径混淆 |
| **P2（计划）** | Legacy syntax、Declaration | 旧语法可能不被后续工具支持        |
| **P3（可选）** | Naming、Formatting         | 仅影响风格一致性，不影响功能      |

##### Lint 通过标准

- **硬标准**：P0 类问题 = 0；P1 类问题 ≤ 原始数量的 30%
- **软标准**：P2 类问题可纳入技术债跟踪，逐版本收敛
- **豁免标准**：P3 类问题在团队风格规范明确前可保留

#### 7.5.10 Yosys 综合限制与 WSL 环境适配

##### WSL 环境内存限制

在 Windows WSL 环境中运行 Yosys 时，复杂设计的 RTLIL 展开可能因内存不足而卡死或崩溃：

- **现象**：Yosys 在 `read_verilog` / `hierarchy` 阶段超时（60s+），WSL pty 崩溃（`灾难性故障 E_UNEXPECTED`）
- **根因**：WSL 默认使用一半物理内存，大型 always 组合块生成的 RTLIL 网表对象数超标
- **影响阈值**：大规模展开的 always 组合块（如 multi-channel 运算阵列、多级嵌套 generate 块）生成的 RTLIL 网表对象数可能超标

##### 解决方案矩阵

| 策略              | 适用场景          | 操作                                                  |
| ----------------- | ----------------- | ----------------------------------------------------- |
| **分模块综合**    | 子模块可独立综合  | 按 leaf → branch → top 顺序逐级综合                   |
| **WSL 内存扩容**  | 物理内存 ≥ 32GB   | 创建 `%UserProfile%\.wslconfig`，设置 `memory=24GB`   |
| **输出重定向**    | 抑制终端 I/O 延迟 | `yosys ... > out.txt 2>&1`，将 stderr warnings 重定向 |
| **timeout 保护**  | 防止终端卡死      | `timeout 120 yosys ...`                               |
| **Yosys -Q 模式** | 减少输出开销      | 添加 `-Q` 参数抑制 banner 和冗余日志                  |
| **本地 Linux**    | 确保资源充足      | 使用物理 Linux 或云 VM（≥16GB RAM）                   |

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

| 工具    | 安装方式                         | 注意事项                                                 |
| ------- | -------------------------------- | -------------------------------------------------------- |
| Yosys   | `apt-get install yosys`          | 版本可能较旧（Ubuntu 22.04 = 0.9）；手动编译可获取最新版 |
| Verible | GitHub Releases 下载预编译二进制 | 不通过 apt 安装；解压后复制到 `/usr/local/bin`           |
| OpenSTA | AppImage 或源码编译              | SWIG >= 4.x 需修改 CMakeLists.txt 移除版本约束           |
| Icarus  | `apt-get install iverilog`       | 安装简单，无特殊版本需求                                 |

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
localparam MAX_N = 32;  // 最大通道数/元素数

// 使用常量边界 → 工具在编译期确定迭代次数
for (ch = 0; ch < MAX_N; ch = ch + 1) begin
    if (ch < active_n) begin  // 运行时条件：仅活跃元素执行
        channel_data[CH_W*ch +: CH_W] = ...;
    end
end
```

##### 典型修复清单（参考模板）

| 修复位置        | 变量边界                     | 替换为                          | 改动量 |
| --------------- | ---------------------------- | ------------------------------- | ------ |
| 通道遍历循环    | `active`（运行时变量）       | `MAX_N` + `if (ch < active)`    | 1 行   |
| 多维索引遍历    | `n_active`（运行时变量）     | `MAX_M` + `if (n < n_active)`   | 1 行   |
| 数据清零/初始化 | `K * n_active`（运行时起始） | `0` + `if (ch >= K * n_active)` | 1 行   |
| 切片组合遍历    | `fn_a`/`fn_b`（运行时变量）  | `MAX_A`/`MAX_B` + 条件分支      | 2-4 行 |

##### 设计规则

> **所有综合目标 for 循环必须使用 `localparam` 常量作为边界**。运行时变量差异通过循环体内的 `if` 条件分支处理。新增常量定义统一放置在模块参数声明区，以 `MAX_` 前缀命名以便识别。

#### 7.5.12 综合警告诊断：范围越界

##### 警告特征

```
Warning: Range select [N:M] out of bounds on signal `\<signal_name>':
Setting all (N-M+1) result bits to undef.
```

##### 诊断三步法

**Step 1: 定位**。识别警告涉及的信号和越界偏移量：

- 信号名：报告中的信号全路径名
- 越界范围：`[N:M]`
- 信号声明位宽：`[W_MAX - 1:0]`（记下最大值）

**Step 2: 分析**。追踪越界访问的生成逻辑：

```
越界访问通常源于以下模式：
  1. 展开比率估算不足：索引公式中乘了展开因子（如 4×、8×）
     但信号位宽未同步放大
  2. 条件分支生成的访问路径：某些 mode 下索引偏移超出声明范围
  3. 参数化表达式中边界计算错误
```

**Step 3: 修复**。重新计算所需位宽：

```verilog
// 修复前
wire [W_MAX - 1:0] unpacked_data;           // 未考虑展开率

// 修复后：将展开率纳入位宽计算
localparam UNPACK_RATIO = 4;                 // 最大展开倍数
wire [W_MAX * UNPACK_RATIO - 1:0]
     unpacked_data;                           // 位宽 × 展开率
```

##### 通用诊断原则

| 警告类型                   | 诊断方法                             | 修复策略                            |
| -------------------------- | ------------------------------------ | ----------------------------------- |
| range select out of bounds | 对比信号声明位宽与访问偏移           | 扩容信号位宽或限制访问范围          |
| inferred latch             | 检查 case/if 完整性                  | 补全 else/default 分支              |
| multi-driver               | 查 grep `信号名` 的 assign/always 源 | 合并到单一 always 块                |
| blackbox                   | `hierarchy -check` 未解析            | 补充子模块源文件或 `-blackbox` 声明 |

---

## Phase 8: AI 波形调试工作流

### 8.1 debug_waveform.py — 零依赖 VCD 分析工具

本目录下的 `debug_waveform.py` 是专为 AI 代理设计的 VCD 波形分析器，无需安装任何额外 Python 包（仅使用标准库）。所有命令输出结构化 JSON，便于程序化解析。

#### 快速上手

```bash
# 1. 运行仿真，生成 VCD 波形文件
iverilog -o simv rtl/*.v tb/*.v && vvp simv

# 2. 自动发现快照（调试起点）
python3 debug_waveform.py --vcd dump.vcd --watch

# 3. 列出所有信号（定位目标）
python3 debug_waveform.py --vcd dump.vcd --list-signals

# 4. 定向快照 + 时序追踪（深入排查）
python3 debug_waveform.py --vcd dump.vcd --watch result valid --time 95000 --json
python3 debug_waveform.py --vcd dump.vcd --watch result --trigger valid -n 20
```

#### 命令参考

| 用法                                | 场景                          | 典型输出               |
| ----------------------------------- | ----------------------------- | ---------------------- |
| `--watch`                           | 自动发现快照（仿真结束时刻）  | 全部信号的当前值       |
| `--watch <sig1> <sig2> --time <ps>` | 指定时刻的定向快照            | 指定信号的定点值       |
| `--watch <sig> --time T1-T2`        | 时间窗口内信号变化追踪        | 窗口内所有变化的时间线 |
| `--watch <sig> --trigger <沿> -n N` | 触发沿时序追踪                | 触发后 N 次变化序列    |
| `--list-signals`                    | 列出 VCD 中所有信号及层级路径 | 信号名列表（含层级）   |
| `--list-signals --pattern <kw>`     | 按关键词筛选信号              | 匹配的信号名列表       |

#### 调试场景速查

| 场景                   | 推荐命令                                | 说明                             |
| ---------------------- | --------------------------------------- | -------------------------------- |
| 仿真结束时检查全部输出 | `--watch`                               | 自动发现模式，无需指定时间和信号 |
| 怀疑某时刻结果错误     | `--watch <信号> --time <ps>`            | 查看该时刻的具体值               |
| 信号异常跳变追踪       | `--watch <sig> --trigger posedge -n 10` | 捕获触发后的变化序列             |
| 窗口内行为分析         | `--watch <sig> --time T1-T2`            | 查看窗口内的所有变化             |
| 信号名不记得           | `--list-signals --pattern <关键词>`     | 搜索信号层级和名称               |
| 多信号同时监控         | `--watch sig_a sig_b --time <ps>`       | 空格分隔多信号                   |
| 子模块内部定位         | `--watch u_submod/* --time <窗口>`      | 聚焦子模块信号群                 |

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
    "result": { "bin": "...", "hex": "0x..." },
    "mode": { "bin": "01", "hex": "0x1" }
  }
}
```
