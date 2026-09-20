| variant | mode | run | ok | seconds | commands | cached | remote | local | manifest |
|---|---|---|---|---|---|---|---|---|---|
| native | local | cold | True | 6628.9 | 193 | 0 | 0 | 193 | IDENTICAL |
| native | local-cache | cold | True | 7038.4 | 193 | 0 | 0 | 193 | IDENTICAL |
| native | local-cache | warm | True | 267.6 | 193 | 191 | 0 | 2 | IDENTICAL |
| native | remote | cold | False | 99.4 | 119 | 0 | 119 | 0 | ? |
| native | remote-cache | cold | False | 61.0 | 119 | 0 | 119 | 0 | ? |
| wrapped | local | cold | True | 6353.6 | 199 | 0 | 0 | 199 | IDENTICAL |
| wrapped | local-cache | cold | True | 6090.9 | 199 | 0 | 0 | 199 | IDENTICAL |
| wrapped | local-cache | warm | True | 235.7 | 199 | 197 | 0 | 2 | IDENTICAL |
