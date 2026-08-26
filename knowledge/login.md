# Padrões de impacto — login

## Autenticação e sessão

**Área:** authentication
**Descrição:** Mudanças no fluxo de login afetam diretamente a criação, validação e expiração de sessões — qualquer alteração na etapa de autenticação se propaga para todo endpoint protegido.
**Riscos típicos:** invalidação acidental de sessões ativas; brecha que permite autenticação sem credenciais completas; inconsistência entre o estado de sessão no cliente e no servidor.
**Dependências comuns:** serviço de sessão, middleware de autorização, endpoints protegidos que assumem um usuário já autenticado.
**Testes recomendados:** login válido, login com credenciais incorretas, expiração de sessão, acesso a rota protegida sem sessão ativa.

## Recuperação de senha

**Área:** password_recovery
**Descrição:** Fluxos de login costumam compartilhar lógica ou dependências com a recuperação de senha (verificação de identidade, tokens temporários, envio de e-mail/SMS).
**Riscos típicos:** token de recuperação reutilizável ou sem expiração; enumeração de usuários via mensagens de erro diferentes para e-mail existente/inexistente.
**Dependências comuns:** serviço de e-mail/SMS, tabela de tokens temporários, política de expiração.
**Testes recomendados:** solicitação de recuperação, uso de token expirado, uso de token já utilizado, enumeração de e-mail.

## Segundo fator de autenticação (2FA/MFA)

**Área:** multi_factor_auth
**Descrição:** Adicionar ou alterar um segundo fator introduz um novo estado intermediário entre "não autenticado" e "autenticado", com implicações para todo o fluxo de sessão existente.
**Riscos típicos:** usuários existentes sem segundo fator cadastrado ficarem bloqueados; fallback inseguro quando o segundo fator falha; perda de acesso quando o dispositivo do segundo fator é perdido.
**Dependências comuns:** provedor de SMS/autenticador, tabela de dispositivos confiáveis, fluxo de recuperação de conta.
**Testes recomendados:** login com 2FA habilitado, migração de usuário existente sem 2FA, recuperação de conta com segundo fator perdido.

## Auditoria e logging de acesso

**Área:** audit_logging
**Descrição:** Login é um dos poucos fluxos onde o registro de auditoria é frequentemente um requisito de conformidade, não só uma boa prática — mudanças no formato do evento de login quebram consumidores downstream desse log.
**Riscos típicos:** perda de rastreabilidade de tentativas de acesso; log estruturado quebrado por mudança de schema sem versionamento.
**Dependências comuns:** pipeline de observabilidade, ferramentas de detecção de anomalia que consomem eventos de login.
**Testes recomendados:** verificação de que login bem-sucedido e falho geram evento de auditoria com os campos esperados.

## Rate limiting e bloqueio de conta

**Área:** brute_force_protection
**Descrição:** Alterações no fluxo de login frequentemente interagem com proteções contra força bruta (contagem de tentativas, bloqueio temporário), que são fáceis de quebrar sem perceber.
**Riscos típicos:** contador de tentativas resetado incorretamente por uma mudança não relacionada; bloqueio permanente por bug em vez de temporário.
**Dependências comuns:** cache/contador de tentativas, política de bloqueio, mecanismo de desbloqueio (manual ou por tempo).
**Testes recomendados:** bloqueio após N tentativas falhas, desbloqueio após o tempo configurado, reset do contador em login bem-sucedido.

## Integração com provedores externos (SSO/OAuth)

**Área:** external_auth_provider
**Descrição:** Quando o login delega para um provedor externo (Google, Microsoft, SSO corporativo), mudanças no fluxo local podem quebrar silenciosamente o mapeamento entre identidade externa e conta interna.
**Riscos típicos:** duplicação de contas quando o mapeamento de identidade externa falha; sessão criada sem validar corretamente o token do provedor.
**Dependências comuns:** biblioteca de OAuth/OIDC, tabela de mapeamento de identidade externa, configuração de client ID/secret por ambiente.
**Testes recomendados:** login via provedor externo, primeiro login criando conta nova, login subsequente reconhecendo conta existente.
