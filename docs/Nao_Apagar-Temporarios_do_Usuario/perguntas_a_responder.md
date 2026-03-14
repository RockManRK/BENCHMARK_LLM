Como dizer se o modelo pode ter ou não acesso a internet?

Eu vi isso aqui:
"""
    Solução (src/core/question_executor.py):
     - ✅ Adicionado "stream": False em _execute_with_structured_output() (linha 368)
     - ✅ Adicionado "stream": False em _execute_traditional() (linha 403)
"""
Porém, acredito que as configurações devam ser as mesmas para structured ou não. Não deveria ter configuração diferente para cada a não ser em coisa que PRECISA ser diferente.

