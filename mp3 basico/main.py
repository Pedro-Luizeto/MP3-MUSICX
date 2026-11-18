"""Player de MP3 com interface de teclado no terminal."""

from __future__ import annotations

import os
import random
import shutil
import sys
import time
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

try:
    import pygame
except ImportError:  # Mostra uma orientação clara se a dependência não estiver instalada.
    pygame = None


PASTA_MUSICAS = Path(__file__).resolve().parent / "musicas"


def habilitar_ansi() -> bool:
    """Ativa cores no console clássico do Windows e informa se ANSI está disponível."""
    if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        return False

    if os.name != "nt":
        return os.environ.get("TERM", "") != "dumb"

    try:
        import ctypes

        saida = ctypes.windll.kernel32.GetStdHandle(-11)
        modo = ctypes.c_uint()
        kernel = ctypes.windll.kernel32
        if not kernel.GetConsoleMode(saida, ctypes.byref(modo)):
            return False
        return bool(kernel.SetConsoleMode(saida, modo.value | 0x0004))
    except (AttributeError, OSError):
        return False


class Cores:
    def __init__(self, ativo: bool) -> None:
        self.ativo = ativo

    def pintar(self, texto: str, codigo: str) -> str:
        if not self.ativo:
            return texto
        return f"\033[{codigo}m{texto}\033[0m"


class Teclado:
    """Le teclas sem Enter em terminais; usa comandos numerados em entradas redirecionadas."""

    TECLAS_ESPECIAIS = {
        "H": "up",
        "P": "down",
        "K": "left",
        "M": "right",
    }

    def __init__(self) -> None:
        self.modo_linha = not sys.stdin.isatty()
        self.config_anterior = None

    def __enter__(self) -> "Teclado":
        if not self.modo_linha and os.name != "nt":
            import termios
            import tty

            fd = sys.stdin.fileno()
            self.config_anterior = (fd, termios.tcgetattr(fd))
            tty.setcbreak(fd)
            nova_config = termios.tcgetattr(fd)
            nova_config[3] &= ~termios.ECHO
            termios.tcsetattr(fd, termios.TCSANOW, nova_config)
        return self

    def __exit__(self, *_: object) -> None:
        if self.config_anterior is not None:
            import termios

            fd, config = self.config_anterior
            termios.tcsetattr(fd, termios.TCSANOW, config)

    def ler(self) -> str | None:
        if self.modo_linha:
            try:
                comando = input("\nComando: ").strip().lower()
            except EOFError:
                return "q"
            return {
                "1": "enter",
                "2": "space",
                "3": "n",
                "4": "p",
                "5": "s",
                "6": "x",
                "0": "q",
            }.get(comando, comando)

        if os.name == "nt":
            import msvcrt

            if not msvcrt.kbhit():
                return None
            tecla = msvcrt.getwch()
            if tecla in ("\x00", "\xe0"):
                return self.TECLAS_ESPECIAIS.get(msvcrt.getwch())
            if tecla == "\r":
                return "enter"
            if tecla == " ":
                return "space"
            if tecla == "\x03":
                return "q"
            return tecla.lower()

        import select

        if not select.select([sys.stdin], [], [], 0)[0]:
            return None
        tecla = sys.stdin.read(1)
        if tecla == "\x1b":
            sequencia = ""
            for _ in range(2):
                pronto, _, _ = select.select([sys.stdin], [], [], 0.01)
                if not pronto:
                    break
                sequencia += sys.stdin.read(1)
            return {"[A": "up", "[B": "down", "[C": "right", "[D": "left"}.get(sequencia)
        if tecla in ("\r", "\n"):
            return "enter"
        if tecla == " ":
            return "space"
        if tecla == "\x03":
            return "q"
        return tecla.lower()


class Player:
    def __init__(self, cores: Cores) -> None:
        self.cores = cores
        self.musicas: list[Path] = []
        self.indice_atual: int | None = None
        self.selecao = 0
        self.estado = "parado"
        self.aleatorio = False
        self.volume = 0.8
        self.historico: list[int] = []
        self.proximas_anteriores: list[int] = []
        self.sacola_aleatoria: list[int] = []
        self.inicio_trecho = 0.0
        self.tempo_acumulado = 0.0
        self.mensagem = "Coloque arquivos .mp3 na pasta musicas."
        self.atualizar_biblioteca()

    def atualizar_biblioteca(self) -> None:
        nome_atual = self.musicas[self.indice_atual].name if self.indice_atual is not None and self.musicas else None
        PASTA_MUSICAS.mkdir(parents=True, exist_ok=True)
        self.musicas = sorted(
            (arquivo for arquivo in PASTA_MUSICAS.iterdir() if arquivo.is_file() and arquivo.suffix.lower() == ".mp3"),
            key=lambda arquivo: arquivo.name.casefold(),
        )
        if nome_atual:
            self.indice_atual = next((i for i, arquivo in enumerate(self.musicas) if arquivo.name == nome_atual), None)
        if self.indice_atual is None and self.estado != "tocando":
            self.selecao = min(self.selecao, max(len(self.musicas) - 1, 0))
        self.sacola_aleatoria.clear()
        self.historico.clear()
        self.proximas_anteriores.clear()

    def _remover_da_sacola(self, indice: int) -> None:
        self.sacola_aleatoria = [item for item in self.sacola_aleatoria if item != indice]

    def _tocar_indice(self, indice: int, *, registrar: bool = True, limpar_futuros: bool = True) -> None:
        if not self.musicas:
            self.mensagem = "Nenhum MP3 encontrado. Adicione arquivos à pasta musicas."
            self.estado = "parado"
            return

        indice %= len(self.musicas)
        anterior = self.indice_atual
        if registrar and anterior is not None and anterior != indice:
            self.historico.append(anterior)
        if limpar_futuros:
            self.proximas_anteriores.clear()
        self.indice_atual = indice
        self.selecao = indice
        self._remover_da_sacola(indice)

        try:
            pygame.mixer.music.load(str(self.musicas[indice]))
            pygame.mixer.music.play()
            pygame.mixer.music.set_volume(self.volume)
        except pygame.error as erro:
            self.estado = "parado"
            self.mensagem = f"Não foi possível tocar {self.musicas[indice].name}: {erro}"
            return

        self.estado = "tocando"
        self.inicio_trecho = time.monotonic()
        self.tempo_acumulado = 0.0
        self.mensagem = f"Tocando: {self.musicas[indice].name}"

    def tocar_selecao(self) -> None:
        if self.musicas:
            self._tocar_indice(self.selecao)

    def alternar_reproducao(self) -> None:
        if self.estado == "tocando":
            pygame.mixer.music.pause()
            self.tempo_acumulado = self.tempo_atual()
            self.estado = "pausado"
            self.mensagem = "Reprodução pausada."
        elif self.estado == "pausado":
            pygame.mixer.music.unpause()
            self.inicio_trecho = time.monotonic()
            self.estado = "tocando"
            self.mensagem = "Reprodução retomada."
        elif self.indice_atual is not None:
            self._tocar_indice(self.indice_atual, registrar=False)
        else:
            self.tocar_selecao()

    def parar(self) -> None:
        pygame.mixer.music.stop()
        self.estado = "parado"
        self.tempo_acumulado = 0.0
        self.mensagem = "Reprodução parada."

    def proxima(self) -> None:
        if not self.musicas:
            self.mensagem = "Nenhum MP3 encontrado na pasta musicas."
            return
        if self.indice_atual is None:
            self._tocar_indice(self.selecao)
            return

        if self.proximas_anteriores:
            indice = self.proximas_anteriores.pop()
        elif self.aleatorio:
            if not self.sacola_aleatoria:
                self.sacola_aleatoria = [i for i in range(len(self.musicas)) if i != self.indice_atual]
                random.shuffle(self.sacola_aleatoria)
                if not self.sacola_aleatoria:
                    self.sacola_aleatoria = [self.indice_atual]
            indice = self.sacola_aleatoria.pop()
        else:
            indice = (self.indice_atual + 1) % len(self.musicas)
        self._tocar_indice(indice)

    def anterior(self) -> None:
        if not self.musicas:
            self.mensagem = "Nenhum MP3 encontrado na pasta musicas."
            return
        if self.indice_atual is None:
            self._tocar_indice(self.selecao)
            return

        if self.historico:
            indice = self.historico.pop()
        elif not self.aleatorio:
            indice = (self.indice_atual - 1) % len(self.musicas)
        else:
            self._tocar_indice(self.indice_atual, registrar=False)
            return
        self.proximas_anteriores.append(self.indice_atual)
        self._tocar_indice(indice, registrar=False, limpar_futuros=False)

    def alternar_aleatorio(self) -> None:
        self.aleatorio = not self.aleatorio
        self.sacola_aleatoria.clear()
        if self.aleatorio and self.indice_atual is not None:
            self.sacola_aleatoria = [i for i in range(len(self.musicas)) if i != self.indice_atual]
            random.shuffle(self.sacola_aleatoria)
        self.mensagem = f"Ordem aleatória {'ativada' if self.aleatorio else 'desativada'}."

    def ajustar_volume(self, delta: float) -> None:
        self.volume = max(0.0, min(1.0, self.volume + delta))
        pygame.mixer.music.set_volume(self.volume)
        self.mensagem = f"Volume: {round(self.volume * 100)}%"

    def atualizar(self) -> None:
        if self.estado == "tocando" and not pygame.mixer.music.get_busy():
            self.proxima()

    def tempo_atual(self) -> float:
        if self.estado == "tocando":
            return self.tempo_acumulado + (time.monotonic() - self.inicio_trecho)
        return self.tempo_acumulado

    def renderizar(self) -> None:
        largura = max(48, min(shutil.get_terminal_size((80, 24)).columns, 100))
        conteudo: list[str] = []
        borda = "+" + "-" * (largura - 2) + "+"
        conteudo.append(self.cores.pintar(borda, "36"))
        conteudo.append(self._centralizar("MP3 PLAYER  |  TERMINAL", largura))
        conteudo.append(self.cores.pintar(borda, "36"))
        conteudo.append("")

        faixa_atual = self.musicas[self.indice_atual].name if self.indice_atual is not None and self.musicas else "Nenhuma faixa selecionada"
        limite_texto = max(18, largura - 12)
        if len(faixa_atual) > limite_texto:
            faixa_atual = faixa_atual[: limite_texto - 3] + "..."
        estado_cor = {"tocando": "32", "pausado": "33", "parado": "90"}.get(self.estado, "37")
        situacao = {"tocando": "TOCANDO", "pausado": "PAUSADO", "parado": "PARADO"}.get(self.estado, "PARADO")
        conteudo.append(self.cores.pintar("  AGORA", "1;36"))
        conteudo.append(f"  {self.cores.pintar(situacao, estado_cor)}  {faixa_atual}")
        conteudo.append(f"  Decorrido: {self._formatar_tempo(self.tempo_atual())}    Volume: {round(self.volume * 100)}%")
        modo = self.cores.pintar("ALEATÓRIO: ON", "1;32") if self.aleatorio else self.cores.pintar("ALEATÓRIO: OFF", "90")
        conteudo.append(f"  Ordem: {modo}    Biblioteca: {len(self.musicas)} faixa(s)")
        conteudo.append("")
        conteudo.append(self.cores.pintar("  BIBLIOTECA", "1;36"))

        if not self.musicas:
            conteudo.append("  Sua pasta musicas está vazia. Coloque arquivos .mp3 nela e pressione R.")
        else:
            altura = max(3, shutil.get_terminal_size((80, 24)).lines - 18)
            altura = min(altura, 12)
            inicio = max(0, min(self.selecao - altura // 2, len(self.musicas) - altura))
            for indice in range(inicio, min(inicio + altura, len(self.musicas))):
                selecionada = indice == self.selecao
                atual = indice == self.indice_atual
                marcador = ">" if selecionada else " "
                tocando = " [tocando]" if atual and self.estado == "tocando" else ""
                nome = self.musicas[indice].name
                limite_nome = max(12, largura - 25)
                if len(nome) > limite_nome:
                    nome = nome[: limite_nome - 3] + "..."
                linha = f"  {marcador} {indice + 1:02d}. {nome}{tocando}"
                conteudo.append(self.cores.pintar(linha, "1;32" if selecionada else ("36" if atual else "37")))
            if len(self.musicas) > altura:
                conteudo.append(f"  Mostrando {inicio + 1}-{min(inicio + altura, len(self.musicas))} de {len(self.musicas)}")

        conteudo.append("")
        if self.mensagem:
            mensagem = self.mensagem
            if len(mensagem) > largura - 4:
                mensagem = mensagem[: largura - 7] + "..."
            conteudo.append("  " + self.cores.pintar(mensagem, "90"))
        conteudo.append("")
        conteudo.append(self.cores.pintar("  CONTROLES", "1;36"))
        if sys.stdin.isatty():
            conteudo.append("  ↑/↓ selecionar   Enter tocar   Espaço pausar/retomar   N próxima   P anterior")
            conteudo.append("  S aleatório   X parar   +/- volume   R atualizar pasta   Q sair")
        else:
            conteudo.append("  1 tocar   2 pausar/retomar   3 próxima   4 anterior   5 aleatório")
            conteudo.append("  6 parar   0 sair   R atualizar pasta")

        limpar = "\033[2J\033[H" if sys.stdout.isatty() and os.environ.get("TERM") != "dumb" else ""
        sys.stdout.write(limpar + "\n".join(conteudo) + "\n")
        sys.stdout.flush()

    def _centralizar(self, texto: str, largura: int) -> str:
        espacos = max(0, (largura - len(texto) - 2) // 2)
        return "|" + " " * espacos + self.cores.pintar(texto, "1;37") + " " * max(0, largura - len(texto) - espacos - 2) + "|"

    @staticmethod
    def _formatar_tempo(segundos: float) -> str:
        total = max(0, int(segundos))
        return f"{total // 60:02d}:{total % 60:02d}"

    def executar(self) -> None:
        ultima_renderizacao = 0.0
        with Teclado() as teclado:
            try:
                while True:
                    self.atualizar()
                    agora = time.monotonic()
                    if agora - ultima_renderizacao >= 0.5:
                        self.renderizar()
                        ultima_renderizacao = agora

                    tecla = teclado.ler()
                    if tecla == "q":
                        break
                    if tecla == "up" and self.musicas:
                        self.selecao = (self.selecao - 1) % len(self.musicas)
                    elif tecla == "down" and self.musicas:
                        self.selecao = (self.selecao + 1) % len(self.musicas)
                    elif tecla == "enter":
                        self.tocar_selecao()
                    elif tecla == "space":
                        self.alternar_reproducao()
                    elif tecla == "n":
                        self.proxima()
                    elif tecla == "p":
                        self.anterior()
                    elif tecla == "s":
                        self.alternar_aleatorio()
                    elif tecla == "x":
                        self.parar()
                    elif tecla in ("+", "="):
                        self.ajustar_volume(0.05)
                    elif tecla in ("-", "_"):
                        self.ajustar_volume(-0.05)
                    elif tecla == "r":
                        self.atualizar_biblioteca()
                        self.mensagem = f"Biblioteca atualizada: {len(self.musicas)} faixa(s)."
                    elif tecla:
                        self.mensagem = "Tecla desconhecida. Use os controles exibidos na tela."
                    if tecla:
                        self.renderizar()
                        ultima_renderizacao = time.monotonic()
                    time.sleep(0.03)
            except KeyboardInterrupt:
                pass
            finally:
                pygame.mixer.music.stop()
                sys.stdout.write("\033[0m\nPlayer encerrado. Até mais!\n")
                sys.stdout.flush()


def main() -> int:
    if pygame is None:
        print("Dependência ausente. Instale com: python -m pip install -r requirements.txt")
        return 1

    cores = Cores(habilitar_ansi())
    try:
        pygame.mixer.init()
    except pygame.error as erro:
        print(f"Não foi possível iniciar o áudio: {erro}")
        print("Confira a saída de áudio do computador e tente novamente.")
        return 1

    try:
        Player(cores).executar()
    finally:
        pygame.mixer.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
