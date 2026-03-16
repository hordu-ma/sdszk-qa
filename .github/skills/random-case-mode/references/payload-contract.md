# Payload Contract

> 基础设施与部署请参考：`src/infra/README.md`。

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
