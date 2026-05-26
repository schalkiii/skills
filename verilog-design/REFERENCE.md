# Verilog RTL 设计方法学 — 完整参考

## Phase 0：硬件思维方法论

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

## 第一阶段：规格与架构

### 1.1 先定义接口契约

在编写任何 RTL 代码之前，必须明确：

- **接口**：所有端口的信号方向、位宽和行为
- **模式/功能**：枚举所有操作模式
- **时序**：流水线深度、延迟、吞吐量要求
- **特殊情况**：零、无穷大、溢出、下溢、复位行为
- **数据格式**：位域定义（如 IEEE 754 FP16：符号[15] + 指数[14:10] + 尾数[9:0]）

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

---

## 第二阶段：RTL 编码

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

## 第三阶段：数值系统规范

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

#### 特殊值处理

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

#### 单路径指数计算

```verilog
// 错误：运行时分支产生两条并行数据路径
s5_exp = max_exp - FP16_BIAS;
if (leading_pos > FRAC_BITS)
    s5_exp = s5_exp + (leading_pos - FRAC_BITS);

// 正确：单条算术路径。leading_pos == FRAC_BITS 时加 0，等价空操作
s5_exp = max_exp + leading_pos - FRAC_BITS - FP16_BIAS;
```

---

## 第四阶段：测试平台方法学

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

---

## 第五阶段：调试技术

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

## 第六阶段：风格与最佳实践

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

## 第七阶段：综合与物理设计

### 7.1 开源 EDA 工具链（Windows + WSL）

所有开源 EDA 工具均为 Linux 原生。Windows 下通过 WSL 运行：

```powershell
wsl bash -c "make sim"
wsl bash -c "make synth"
```

工具链：

```
仿真        → Icarus Verilog (iverilog) + vvp
波形        → Verdi (FSDB) / GTKWave (VCD)
综合        → Yosys + OpenSTA
布局布线    → OpenROAD
逻辑等价性  → Yosys (equiv_*)
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

### 7.4 Makefile 集成

```makefile
VERILOG_SOURCES := $(wildcard rtl/*.v) params.vh
TESTBENCH := tb/tb_top.v

syn: $(VERILOG_SOURCES)
  yosys -p "read_verilog -sv params.vh rtl/dut.v; hierarchy -top top_module; proc; opt; stat; write_verilog syn_output.v"

sta: syn_output.v
  sta sta.tcl

sim: $(VERILOG_SOURCES) $(TESTBENCH)
  iverilog -g2012 -o simv $(VERILOG_SOURCES) $(TESTBENCH)
  vvp simv
```

---

## 第八阶段：AI 波形调试工作流

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
