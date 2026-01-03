# 🚀 Guia de Uso: jellyfix-batch

Script para processar múltiplas pastas de mídia em paralelo.

## 📦 Instalação

O script já está incluído em `/usr/bin/jellyfix-batch` após instalar o pacote.

## 💡 Uso Básico

### 1. Processar pastas no diretório atual

```bash
# Entrar no diretório com as pastas
cd /home/jellycp/JellyContos/Series/

# Processar 3 séries
jellyfix-batch BreakingBad TheOffice GameOfThrones
```

### 2. Testar primeiro (dry-run)

```bash
# Modo simulação - NÃO modifica arquivos
jellyfix-batch -n Serie1 Serie2 Serie3
```

### 3. Processar com caminhos absolutos

```bash
jellyfix-batch \
    /media/Series/BreakingBad \
    /media/Series/TheOffice \
    /media/Filmes/Matrix
```

### 4. Processar com wildcard (glob)

```bash
# Processar todas as pastas que começam com "Breaking"
cd /media/Series/
jellyfix-batch Breaking*

# Processar TUDO no diretório atual
jellyfix-batch */
```

## ⚙️ Opções Disponíveis

```bash
-j, --jobs NUM        Número de jobs paralelos (padrão: 5)
-n, --dry-run         Modo simulação (não modifica)
-v, --verbose         Saída detalhada
-l, --log-dir DIR     Diretório para logs
-f, --ffprobe         Usar ffprobe para qualidade
-h, --help            Mostrar ajuda
```

## 🎯 Exemplos Práticos

### Processar 10 séries ao mesmo tempo

```bash
cd /media/Series/
jellyfix-batch -j 10 Serie*
```

### Processar com verbose e ffprobe

```bash
jellyfix-batch -v -f \
    "/media/Series/Breaking Bad" \
    "/media/Series/The Office"
```

### Testar sem modificar nada

```bash
# Primeiro teste com dry-run
jellyfix-batch -n Serie1 Serie2 Serie3

# Se estiver tudo OK, execute de verdade
jellyfix-batch Serie1 Serie2 Serie3
```

### Processar tudo em um diretório

```bash
cd /media/Series/
jellyfix-batch */
```

### Salvar logs em local específico

```bash
jellyfix-batch -l ~/logs/jellyfix Serie1 Serie2
```

## 📊 Como Funciona

1. **Validação**: Verifica se as pastas existem
2. **Confirmação**: Pede confirmação (se não for dry-run)
3. **Processamento**: Executa em paralelo (padrão: 5 jobs)
4. **Logs**: Salva log individual para cada pasta
5. **Resumo**: Mostra estatísticas ao final

## 📁 Logs

Logs são salvos em `/tmp/jellyfix-logs/` por padrão:

```bash
# Ver logs
ls -lh /tmp/jellyfix-logs/

# Acompanhar em tempo real
tail -f /tmp/jellyfix-logs/*.log

# Ver log específico
cat /tmp/jellyfix-logs/20260103_123456_BreakingBad.log
```

## ⚡ Performance

- **5 jobs** (padrão): Bom para SSDs, uso moderado de CPU
- **10 jobs**: Máximo para sistemas potentes
- **1 job**: Processamento sequencial (mais lento)

```bash
# Ajustar conforme seu hardware
jellyfix-batch -j 10 Serie*  # Muitos jobs
jellyfix-batch -j 1 Serie*   # Um por vez
```

## 🔧 Configurações

As configurações são lidas de `~/.jellyfix/config.json`:

```json
{
  "tmdb_api_key": "sua_chave",
  "kept_languages": ["eng", "por"],
  "remove_language_variants": true,
  "rename_por2": true,
  "rename_no_lang": true,
  "remove_foreign_subs": true,
  "organize_folders": true,
  "fetch_metadata": true,
  "rename_nfo": true,
  "min_pt_words": 5
}
```

## 🚨 Dicas Importantes

### ✅ FAÇA

- Sempre teste com `-n` primeiro
- Use caminhos absolutos para scripts automatizados
- Ajuste `-j` conforme seu hardware
- Verifique os logs após processar

### ❌ NÃO FAÇA

- Não processe sem backup
- Não use muitos jobs em HDs mecânicos
- Não cancele no meio (Ctrl+C funciona, mas pode deixar arquivos pela metade)

## 📝 Exemplos do Mundo Real

### Organizar biblioteca completa de séries

```bash
#!/bin/bash
# organize-series.sh

cd /home/jellycp/JellyContos/Series/

# Primeiro, dry-run para ver o que vai acontecer
jellyfix-batch -n -v */ > preview.txt

# Revisar
less preview.txt

# Se OK, executar
jellyfix-batch -j 8 */
```

### Processar apenas pastas não organizadas

```bash
#!/bin/bash
# Processar apenas pastas SEM [tmdbid-*]

cd /media/Series/

for dir in */; do
    if [[ ! "$dir" =~ \[tmdbid-[0-9]+\] ]]; then
        jellyfix-batch "$dir"
    fi
done
```

### Script de manutenção mensal

```bash
#!/bin/bash
# monthly-organize.sh

LOG_DIR=~/logs/jellyfix-$(date +%Y%m)
mkdir -p "$LOG_DIR"

# Processar com logs organizados por mês
jellyfix-batch -j 10 -l "$LOG_DIR" \
    /media/Series/* \
    /media/Filmes/*

# Enviar relatório
mail -s "Jellyfix: Organização Mensal" user@example.com < "$LOG_DIR"/summary.txt
```

## 🆘 Troubleshooting

### "Nenhuma pasta válida encontrada"

- Verifique se está no diretório correto
- Use caminhos absolutos ou `pwd` para confirmar
- Teste: `ls -ld pasta1 pasta2`

### Jobs muito lentos

- Reduza número de jobs: `-j 3`
- Verifique uso de CPU/disco: `htop`
- Desative ffprobe se não precisar

### Erros nos logs

```bash
# Ver apenas erros
grep -i "error\|fail" /tmp/jellyfix-logs/*.log

# Ver resumo de cada log
for log in /tmp/jellyfix-logs/*.log; do
    echo "=== $(basename $log) ==="
    tail -10 "$log"
done
```

## 📚 Mais Informações

- Documentação completa: `jellyfix --help`
- Configuração interativa: `jellyfix` (sem args)
- GUI: `jellyfix-gui`
