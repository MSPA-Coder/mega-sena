# Arquitetura

## Visão geral

O projeto é uma aplicação Flask monolítica e modular. A separação por
funcionalidade mantém o fluxo HTTP, as regras da aplicação e a persistência
compreensíveis sem adicionar abstrações que o tamanho atual não exige.

```text
navegador -> app/web -> serviços de bets, draws ou settings -> SQLAlchemy
                         |                           |
                         +-------- app/core --------+
```

Essa direção é uma orientação de projeto, não uma API imutável. Uma mudança
pode atravessar camadas quando houver motivo claro, desde que as regras de
negócio continuem testáveis fora das rotas e a transação permaneça explícita.

## Inicialização

`app.create_app()` compõe a aplicação, aplica a configuração, inicializa
SQLAlchemy e Flask-Migrate, registra as rotas e prepara o banco. Configurações
podem ser substituídas no factory, o que permite bancos temporários nos testes e
outros ambientes de execução.

Na inicialização, `app/schema.py` aplica as migrações do Alembic até a
revisão mais recente (`flask db upgrade`), tanto em um banco novo quanto em um
já existente. O PostgreSQL é o único backend de execução suportado — a suíte
de testes isolada usa SQLite em memória apenas por não exigir infraestrutura
externa, e o job `postgres-smoke` do CI valida as migrações contra um
PostgreSQL real. Backups de dados são feitos fora do processo de
inicialização, com `pg_dump`/`scripts/backup_postgres.ps1`.

## Módulos

### `app/web/`

Converte requisições em chamadas da aplicação e respostas Flask. As rotas são
agrupadas por tela: dashboard, concursos, apostas e configurações. Validação
específica de HTTP, mensagens, redirects e renderização pertencem a essa camada.

### `app/bets/`

- `criteria.py` normaliza e avalia os critérios de geração;
- `service.py` gera, valida, grava e consulta apostas;
- `combinatorics.py` calcula universo, cobertura e parâmetros sugeridos.

`GenerationCriteria` reúne os campos e as relações entre filtros para que a
mesma interpretação seja usada na interface, na geração e nos relatórios.

### `app/draws/`

- `importing.py` lê planilhas e atualiza os concursos de forma transacional;
- `statistics.py` calcula as agregações do dashboard;
- `service.py` fornece as consultas usadas pela interface.

### `app/settings/`

Mantém os valores padrão da geração e as operações de manutenção solicitadas
pela tela de configurações.

### `app/core/`

Contém funções compartilhadas de números, formatação e segurança HTTP. Código
específico de uma funcionalidade deve ficar no respectivo pacote, mesmo quando
for reutilizado por mais de uma rota.

### Persistência e interface

`app/models.py` contém os três modelos atuais: concursos, apostas geradas e
configurações. Separar cada modelo ou introduzir repositories só se justifica
quando isso reduzir complexidade observável.

Templates são agrupados por página em `app/templates/`. O CSS parte de tokens e
componentes compartilhados em `app/static/css/`, com arquivos específicos para
as páginas. Scripts ficam em arquivos estáticos e são carregados com `defer`.

## Princípios de evolução

- regras reutilizáveis ficam em funções ou serviços testáveis sem uma requisição;
- rotas coordenam o caso de uso, mas não concentram consultas ou cálculos extensos;
- alterações persistentes usam migrações versionadas;
- limites operacionais ficam próximos da validação que os aplica e têm uma razão
  de segurança, desempenho ou experiência do usuário;
- compatibilidade é mantida quando existe consumidor conhecido, não apenas para
  conservar a forma interna de versões anteriores;
- abstrações e novos padrões são adotados quando simplificam uma necessidade
  concreta do código atual.
