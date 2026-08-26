# Padrões de impacto — notificação

## Canais múltiplos (email, push, SMS)

**Área:** multi_channel_delivery
**Descrição:** Uma notificação nova costuma precisar ser adaptada para múltiplos canais de entrega, cada um com limitações próprias de formato e tamanho.
**Riscos típicos:** conteúdo formatado para e-mail quebrando em push notification (limite de caracteres); canal específico esquecido na implementação de uma notificação que deveria cobrir todos.
**Dependências comuns:** provedores de e-mail, push e SMS, template por canal.
**Testes recomendados:** entrega em cada canal suportado, truncamento correto de conteúdo longo, fallback quando um canal específico falha.

## Preferências do usuário e opt-out

**Área:** user_preferences
**Descrição:** Notificações precisam respeitar preferências de opt-in/opt-out do usuário — uma notificação nova pode ser enviada sem checar essa preferência se o desenvolvedor não souber que ela existe.
**Riscos típicos:** notificação enviada ignorando opt-out explícito do usuário (risco de conformidade, não só de qualidade); ausência de opção de desativar o tipo de notificação novo.
**Dependências comuns:** tabela de preferências de notificação, mecanismo de opt-out (link de descadastro, configuração no app).
**Testes recomendados:** notificação não enviada após opt-out, opção de preferência visível para o novo tipo de notificação, opt-out aplicado por canal quando aplicável.

## Deduplicação e agrupamento

**Área:** deduplication
**Descrição:** Eventos que disparam a mesma notificação múltiplas vezes em curto período devem ser agrupados ou deduplicados — sem isso, o usuário recebe spam do próprio sistema.
**Riscos típicos:** notificação duplicada por reprocessamento do mesmo evento; ausência de agrupamento gerando dezenas de notificações individuais quando uma agregada seria mais útil.
**Dependências comuns:** identificador de evento para deduplicação, janela de agrupamento configurável.
**Testes recomendados:** evento reprocessado não gerando notificação duplicada, múltiplos eventos relacionados agrupados numa notificação, comportamento no limite da janela de agrupamento.

## Falhas de entrega e retry

**Área:** delivery_failure_handling
**Descrição:** Provedores de notificação (e-mail, push, SMS) falham com frequência maior que APIs internas — o tratamento de falha de entrega é parte central do requisito, não um detalhe.
**Riscos típicos:** falha de entrega silenciosa sem retry nem log; retry sem limite, reenviando indefinidamente uma notificação que sempre falha pelo mesmo motivo.
**Dependências comuns:** fila de retry, provedor de notificação, métrica de taxa de falha por canal.
**Testes recomendados:** retry limitado após falha de entrega, log/métrica de falha registrada, comportamento quando o provedor está indisponível.

## Templates e localização

**Área:** template_localization
**Descrição:** Alterar o conteúdo ou variáveis de um template de notificação afeta todos os idiomas suportados simultaneamente, e um placeholder esquecido quebra a mensagem inteira.
**Riscos típicos:** variável de template não substituída, aparecendo literalmente na notificação enviada; tradução ausente para o idioma do usuário, caindo silenciosamente no idioma padrão.
**Dependências comuns:** sistema de templates, arquivos de tradução por idioma.
**Testes recomendados:** renderização do template com todas as variáveis preenchidas, notificação em cada idioma suportado, comportamento com variável ausente.

## Testes de fila e taxa de envio

**Área:** queue_throughput
**Descrição:** Uma notificação disparada para um volume grande de usuários de uma vez (broadcast) exige controle de taxa de envio para não sobrecarregar o provedor nem ser marcada como spam.
**Riscos típicos:** broadcast sem controle de taxa, excedendo o limite do provedor e causando bloqueio temporário da conta de envio; fila crescendo sem limite sob pico, atrasando notificações críticas.
**Dependências comuns:** fila de envio, limite de taxa do provedor, priorização entre notificações críticas e não-críticas.
**Testes recomendados:** envio em broadcast respeitando o limite de taxa do provedor, priorização de notificação crítica sob fila congestionada, comportamento ao atingir o limite do provedor.
