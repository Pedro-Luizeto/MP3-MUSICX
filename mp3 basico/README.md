# MP3 Player no Terminal

Player de MP3 com menu colorido e controles pelo teclado. As músicas ficam na pasta `musicas` ao lado do `main.py`.

## Como iniciar

1. Instale o Python 3.10 ou mais recente.
2. No terminal, dentro desta pasta, instale a dependência:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Coloque arquivos `.mp3` na pasta `musicas`.
4. Inicie o player:

   ```powershell
   python main.py
   ```

## Controles

| Tecla | Ação |
| --- | --- |
| `↑` / `↓` | Selecionar uma música |
| `Enter` | Tocar a música selecionada |
| `Espaço` | Pausar ou continuar |
| `N` | Próxima música |
| `P` | Música anterior |
| `S` | Ativar ou desativar a ordem aleatória |
| `X` | Parar |
| `+` / `-` | Aumentar ou diminuir o volume |
| `R` | Atualizar a biblioteca após adicionar músicas |
| `Q` | Sair |

No modo aleatório, cada faixa é escolhida uma vez antes de a lista embaralhada recomeçar. Ao terminar uma faixa, a próxima começa automaticamente.
