# AES 自写设计

> 状态：A1 待开工。目标：删除 `crypto/third_party/aes`（2 文件 / 674 行，tiny-AES），
> 用第一方 AES 实现替换。

## 1. 现状

- 包装层：`crypto/src/aes128.c` 暴露 `qw_crypto_aes128_ecb_encrypt/decrypt`，
  内部调用 tiny-AES 的 `AES_init_ctx` / `AES_ECB_decrypt` / `AES_ECB_encrypt`。
- 调用方：
  - `audio/src/formats/audio/ncm_crypto.c`（NCM 音乐解密）；
  - `document/src/backends/pdf_reader.c`（PDF 加密流解密，第 1393/1475 行附近）。
- 公共 API：`quirewise/crypto.h` 中的 AES-128 ECB 两个入口，签名不变。

## 2. 目标结构

```
crypto/src/aes.c       AES-128 密钥扩展、块加/解密、S-box 与逆 S-box 表
crypto/src/aes128.c    （保留）ECB 循环、参数校验、状态码映射
```

预估 450–600 行；不新增公共符号，不改变 `QW_CRYPTO_*` 错误码。

## 3. 实现要点

1. 密钥扩展（AES-128：10 轮，11 组轮密钥）；
2. 加密/解密块：SubBytes、ShiftRows、MixColumns、AddRoundKey（解密逆行变换）；
3. 表实现或常量时间实现二选一：优先按位运算 + 预生成 S-box，避免数据相关分支
   （当前用途为文件解密，非侧信道敏感；仍保持简单常量时间写法）；
4. 分块循环与长度校验保持现状（必须是 16 的倍数，空输入合法）。

## 4. 里程碑

| 里程碑 | 内容 | 门禁 | 预估 |
|---|---|---|---|
| **A1** | 自写 AES-128 + 删除 `third_party/aes` | FIPS-197 C.1/C.2/C.3 与 NIST SP 800-38A ECB 向量通过；NCM 与 PDF 解密回归通过；门禁白名单删除 2 条 | 1 人日 |

## 5. 测试与差分

- 已知答案：FIPS-197 附录 C 三组密钥/明文/密文；NIST SP 800-38A ECB 四组向量。
- 回归：`tests/test_crypto.c` 现有 AES 断言；NCM 真实样本解密；PDF 加密样本读取。
- 差分（替换前生成）：对随机 1 MiB 数据用 tiny-AES 加密并记录 SHA-256，
  替换后同密钥同数据结果必须逐字节一致。
- 资源与错误：NULL 参数、非 16 倍数长度、超长输入的错误码保持不变。

## 6. 非目标

- 不新增 AES-CBC/GCM/CTR 等模式（需求出现时单独立项）；
- 不改变 `quirewise/crypto.h` 的已发布函数集合；
- 不把 AES 移到其他包，Crypto 仍是唯一持有者。
