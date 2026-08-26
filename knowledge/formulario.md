# Padrões de impacto — formulário

## Validação client-side vs. server-side

**Área:** validation_layers
**Descrição:** Formulários costumam duplicar regra de validação no cliente (feedback imediato) e no servidor (garantia real) — mudar uma sem a outra cria comportamento inconsistente.
**Riscos típicos:** validação client-side liberando envio que o servidor rejeita silenciosamente; regra de negócio só aplicada no cliente, contornável via chamada direta à API.
**Dependências comuns:** camada de UI, endpoint de submissão, schema de validação compartilhado (se existir).
**Testes recomendados:** envio via UI respeitando a validação, envio direto à API contornando a UI, mensagens de erro consistentes entre as duas camadas.

## Acessibilidade

**Área:** accessibility
**Descrição:** Alterar a estrutura de um formulário (ordem de campos, labels, mensagens de erro) tem impacto direto em usuários de leitor de tela e navegação por teclado.
**Riscos típicos:** campo sem label associado corretamente; erro de validação não anunciado para tecnologia assistiva; ordem de tabulação quebrada.
**Dependências comuns:** biblioteca de componentes de formulário, padrões de ARIA já em uso no restante da aplicação.
**Testes recomendados:** navegação completa por teclado, leitura por leitor de tela dos rótulos e erros, contraste de mensagens de validação.

## Persistência de rascunho

**Área:** draft_persistence
**Descrição:** Formulários longos frequentemente salvam rascunho automaticamente — uma mudança no schema de campos pode quebrar a compatibilidade com rascunhos já salvos.
**Riscos típicos:** rascunho antigo com campo removido causando erro ao carregar; perda silenciosa de dados de rascunho ao migrar schema.
**Dependências comuns:** armazenamento de rascunho (local ou servidor), lógica de merge entre rascunho salvo e schema atual.
**Testes recomendados:** salvar e recuperar rascunho, carregar rascunho salvo antes de uma mudança de schema, comportamento com campo obsoleto no rascunho.

## Migração de schema de dados

**Área:** schema_migration
**Descrição:** Adicionar, remover ou renomear campo num formulário quase sempre exige migração de dados já submetidos anteriormente.
**Riscos típicos:** campo renomeado sem migrar os dados existentes, perdendo o valor histórico; novo campo obrigatório sem valor default para registros antigos.
**Dependências comuns:** script de migração, processo de relatórios/exportações que leem os campos do formulário.
**Testes recomendados:** leitura de registro submetido antes da mudança, migração aplicada corretamente, relatório gerado sem quebrar com o novo schema.

## Internacionalização

**Área:** i18n
**Descrição:** Mudar texto, formato de data/número ou ordem de campos num formulário internacionalizado exige atualização coordenada em todos os idiomas suportados.
**Riscos típicos:** label ou mensagem de erro sem tradução, caindo no idioma padrão inesperadamente; formato de data/número incompatível com a localidade do usuário.
**Dependências comuns:** arquivos de tradução, biblioteca de formatação de data/número por localidade.
**Testes recomendados:** formulário em cada idioma suportado, formatação de campos numéricos/data por localidade, fallback de tradução ausente.

## Testes de campos condicionais

**Área:** conditional_fields
**Descrição:** Campos que aparecem ou tornam-se obrigatórios condicionalmente (com base em outra resposta) são uma fonte comum de bugs de validação não cobertos por testes simples.
**Riscos típicos:** campo condicional obrigatório não validado quando a condição muda dinamicamente; estado inconsistente quando o usuário volta e altera a resposta que disparou a condição.
**Dependências comuns:** lógica de exibição condicional na UI, validação server-side espelhando a mesma condição.
**Testes recomendados:** preenchimento respeitando cada ramo condicional, alteração da resposta-gatilho após preencher o campo condicional, validação server-side da condição.
