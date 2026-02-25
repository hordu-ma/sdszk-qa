# Payload Contract

> 生产部署统一入口：`生产部署指南.md`。

Required core fields:

- `title`
- `difficulty`
- `department`
- `patient_info`
- `chief_complaint`
- `present_illness`
- `past_history`
- `physical_exam`
- `available_tests`
- `standard_diagnosis`
- `key_points`

Compatibility rule:

- Every `recommended_tests` item must be present in `available_tests[].type`.
