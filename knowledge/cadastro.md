# Padrões de impacto — cadastro

## Validação de dados obrigatórios

**Área:** data_validation
**Descrição:** Alterar campos obrigatórios num cadastro afeta todo consumidor downstream que assume a presença desses dados — inclusive registros já existentes, criados sob a regra antiga.
**Riscos típicos:** registros antigos ficarem inconsistentes com a nova regra de validação; validação client-side e server-side divergirem.
**Dependências comuns:** schema do banco, formulário de UI, integrações que consomem o cadastro (faturamento, CRM).
**Testes recomendados:** cadastro com todos os campos, cadastro sem campo recém-tornado obrigatório, leitura de registro antigo sem o campo novo.

## Duplicidade e unicidade de registro

**Área:** uniqueness_constraint
**Descrição:** Mudanças no critério de unicidade (e-mail, documento, nome de usuário) podem gerar conflito com dados já existentes ou abrir brecha para duplicidade.
**Riscos típicos:** constraint de unicidade não aplicada retroativamente a dados legados; condição de corrida permitindo dois cadastros simultâneos com o mesmo identificador.
**Dependências comuns:** índice único no banco, lógica de verificação prévia na aplicação.
**Testes recomendados:** cadastro duplicado sequencial, cadastro duplicado concorrente, cadastro com variação de capitalização/formatação do campo único.

## Integração com serviços de verificação

**Área:** verification_service
**Descrição:** Cadastros costumam depender de verificação externa (confirmação de e-mail, validação de documento, SMS) — uma tool de terceiro no meio do fluxo crítico de onboarding.
**Riscos típicos:** usuário ficar em estado "cadastro incompleto" permanentemente se a verificação falhar sem fallback; custo por verificação aumentando sem controle em picos de cadastro.
**Dependências comuns:** provedor de verificação de e-mail/telefone/documento, fila de reenvio.
**Testes recomendados:** verificação bem-sucedida, verificação expirada, reenvio de verificação, cadastro com serviço de verificação indisponível.

## Dados sensíveis e conformidade (LGPD)

**Área:** sensitive_data_compliance
**Descrição:** Cadastro é tipicamente onde dados pessoais sensíveis entram no sistema pela primeira vez — mudanças aqui têm implicação direta em conformidade com legislação de proteção de dados.
**Riscos típicos:** novo campo sensível coletado sem consentimento explícito; dado sensível logado ou exposto sem necessidade.
**Dependências comuns:** política de retenção de dados, mecanismo de consentimento, processo de exclusão de dados a pedido do titular.
**Testes recomendados:** cadastro com consentimento explícito registrado, exclusão de conta removendo dados sensíveis, ausência de dado sensível em log.

## Fluxo de aprovação ou moderação

**Área:** approval_workflow
**Descrição:** Alguns cadastros exigem aprovação manual ou moderação antes de ficarem ativos — uma mudança no formulário pode não se refletir corretamente na fila de aprovação.
**Riscos típicos:** campo novo não visível para quem aprova; cadastro aprovado automaticamente por engano quando deveria exigir revisão.
**Dependências comuns:** fila/painel de aprovação, notificação ao aprovador, estado "pendente" no registro.
**Testes recomendados:** cadastro entrando em estado pendente, aprovação ativando o cadastro, rejeição comunicada ao solicitante.

## Testes de carga em picos de cadastro

**Área:** load_and_scalability
**Descrição:** Cadastro é um dos fluxos mais sujeitos a picos de tráfego (lançamentos, campanhas) — mudanças que parecem inócuas isoladamente podem não escalar sob carga.
**Riscos típicos:** contenção no índice de unicidade sob alta concorrência; timeout em serviço de verificação externo sob carga não solicitado no dimensionamento original.
**Dependências comuns:** capacidade do banco de dados, limites de taxa do serviço de verificação externo.
**Testes recomendados:** cadastro concorrente em volume, comportamento sob timeout do serviço de verificação, degradação graciosa sob carga acima do esperado.
