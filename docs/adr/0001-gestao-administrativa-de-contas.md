# ADR 0001 — Gestão administrativa de contas

## Decisão

O MegaSena mantém concursos, apostas e configurações como um acervo
compartilhado. A gestão de contas fica restrita ao papel `admin`; contas novas
recebem `operador` por padrão. A primeira conta é criada como administradora
pelo comando de bootstrap. Contas legadas recebem `admin` na migração para
preservar o acesso que já existia.

## Motivo

O controle de acesso necessário é administrativo, não uma partição de dados.
Introduzir `user_id` em apostas, concursos ou configurações teria impacto de
produto e migração muito maior, sem decisão de que esses dados deixariam de
ser compartilhados.

## Proteções

O serviço impede remover o último administrador, desativar o último
administrador ativo, desativar a própria conta ou deixar todas as contas
inativas. Alterações que dependem dessas contagens usam lock transacional no
PostgreSQL. A confirmação visual das ações persistentes permanece no fluxo
HTMX, e CSRF e a autorização são validados no servidor.

## Fora de escopo

Não há exclusão ou migração destrutiva de apostas, concursos ou configurações.
Backup e restauração continuam centralizados no projeto BackupRestore.
