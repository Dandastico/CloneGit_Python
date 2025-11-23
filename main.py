from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Dict, List, Optional, Tuple
import zlib

# --- CAMADA DE OBJETOS DO GIT ---

class ObjetoGit:
    """
    Classe base para qualquer objeto armazenado no Git.
    O Git é um 'content-addressable filesystem', o que significa que
    o nome do arquivo é o Hash SHA-1 do seu conteúdo.
    """
    def __init__(self, tipo_obj: str, conteudo: bytes):
        self.tipo = tipo_obj
        self.conteudo = conteudo

    def calcular_hash(self) -> str:
        """
        Calcula o SHA-1 do objeto.
        O formato é sempre: "tipo tamanho\0conteudo"
        """
        # Exemplo de header: "blob 1024\0"
        cabecalho = f"{self.tipo} {len(self.conteudo)}\0".encode()
        return hashlib.sha1(cabecalho + self.conteudo).hexdigest()

    def serializar(self) -> bytes:
        """
        Comprime o objeto usando Zlib para economizar espaço no disco.
        É assim que os arquivos ficam na pasta .git/objects/
        """
        cabecalho = f"{self.tipo} {len(self.conteudo)}\0".encode()
        return zlib.compress(cabecalho + self.conteudo)

    @classmethod
    def desserializar(cls, dados: bytes) -> ObjetoGit:
        """Lê um arquivo comprimido e reconstrói o objeto Python."""
        descomprimido = zlib.decompress(dados)
        indice_nulo = descomprimido.find(b"\0")
        cabecalho = descomprimido[:indice_nulo].decode()
        conteudo = descomprimido[indice_nulo + 1 :]

        tipo_obj, _ = cabecalho.split(" ")

        return cls(tipo_obj, conteudo)


class Blob(ObjetoGit):
    """
    Representa o CONTEÚDO de um arquivo.
    Nota: O Git não armazena o nome do arquivo no Blob, apenas os dados.
    """
    def __init__(self, conteudo: bytes):
        super().__init__("blob", conteudo)



class Arvore(ObjetoGit):
    """
    Representa um DIRETÓRIO.
    Contém uma lista de associações entre:
    Permissão (Mode) + Nome do Arquivo + Hash do Blob/Tree filho.
    """
    def __init__(self, entradas: List[Tuple[str, str, str]] = None):
        self.entradas = entradas or []
        conteudo = self._serializar_entradas()
        super().__init__("tree", conteudo)

    def _serializar_entradas(self) -> bytes:
        # Formato binário compacto que o Git usa para listar arquivos
        conteudo = b""
        for modo, nome, hash_obj in sorted(self.entradas):
            conteudo += f"{modo} {nome}\0".encode()
            conteudo += bytes.fromhex(hash_obj)

        return conteudo

    def adicionar_entrada(self, modo: str, nome: str, hash_obj: str):
        self.entradas.append((modo, nome, hash_obj))
        self.conteudo = self._serializar_entradas()

    @classmethod
    def a_partir_do_conteudo(cls, conteudo: bytes) -> Arvore:
        # Reconstrói a estrutura de diretório a partir dos bytes brutos
        arvore = cls()
        i = 0
        while i < len(conteudo):
            indice_nulo = conteudo.find(b"\0", i)
            if indice_nulo == -1:
                break

            modo_nome = conteudo[i:indice_nulo].decode()
            modo, nome = modo_nome.split(" ", 1)
            # O hash no Tree é armazenado em binário (20 bytes), convertemos para hex
            hash_obj = conteudo[indice_nulo + 1 : indice_nulo + 21].hex()
            arvore.entradas.append((modo, nome, hash_obj))

            i = indice_nulo + 21

        return arvore


class Commit(ObjetoGit):
    """
    Representa um SNAPSHOT no tempo.
    Aponta para:
    1. Um objeto Tree (o estado raiz dos arquivos)
    2. Commit(s) pai(s) (para formar o histórico)
    3. Metadados (Autor, Data, Mensagem)
    """
    def __init__(
        self,
        hash_arvore: str,
        hashes_pai: List[str],
        autor: str,
        autor_commit: str,
        mensagem: str,
        timestamp: int = None,
    ):
        self.hash_arvore = hash_arvore
        self.hashes_pai = hashes_pai
        self.autor = autor
        self.autor_commit = autor_commit
        self.mensagem = mensagem
        self.timestamp = timestamp or int(time.time())

        conteudo = self._serializar_commit()
        super().__init__("commit", conteudo)

    def _serializar_commit(self):
        # Monta o texto do commit (ex: "tree abc123...\nparent def456...")
        linhas = [f"tree {self.hash_arvore}"]
        for pai in self.hashes_pai:
            linhas.append(f"parent {pai}")

        linhas.append(f"author {self.autor} {self.timestamp} +0000")
        linhas.append(f"committer {self.autor_commit} {self.timestamp} +0000")
        linhas.append("")
        linhas.append(self.mensagem)

        return "\n".join(linhas).encode()

    @classmethod
    def a_partir_do_conteudo(cls, conteudo: bytes) -> Commit:
        # Parser para ler o conteúdo de um commit existente
        linhas = conteudo.decode().split("\n")
        hash_arvore = None
        hashes_pai = []
        autor = None
        autor_commit = None
        inicio_mensagem = 0

        for i, linha in enumerate(linhas):
            if linha.startswith("tree "):
                hash_arvore = linha[5:]
            elif linha.startswith("parent "):
                hashes_pai.append(linha[7:])
            elif linha.startswith("author "):
                partes_autor = linha[7:].rsplit(" ", 2)
                autor = partes_autor[0]
                timestamp = int(partes_autor[1])
            elif linha.startswith("committer "):
                partes_autor_commit = linha[10:].rsplit(" ", 2)
                autor_commit = partes_autor_commit[0]
            elif linha == "":
                inicio_mensagem = i + 1
                break

        mensagem = "\n".join(linhas[inicio_mensagem:])
        commit = cls(hash_arvore, hashes_pai, autor, autor_commit, mensagem, timestamp)
        return commit


# --- GERENCIADOR DO REPOSITÓRIO ---

class Repositorio:
    """
    Gerencia a estrutura de pastas edugit e coordena as operações.
    """
    def __init__(self, caminho="."):
        self.caminho_repo = Path(caminho).resolve()
        self.diretorio_git = self.caminho_repo / "edugit"
        self.diretorio_objetos = self.diretorio_git / "objects" # Onde Blob, Tree e Commit vivem
        self.diretorio_ref = self.diretorio_git / "refs"
        self.diretorio_heads = self.diretorio_ref / "heads" # Onde ficam os ponteiros dos branches (master, main, etc)
        self.arquivo_head = self.diretorio_git / "HEAD" # Ponteiro para o branch atual
        self.arquivo_index = self.diretorio_git / "index" # Staging area (o que vai ser commitado)

    def init(self) -> bool:
        """Cria a estrutura inicial de pastas (edugit/)."""
        if self.diretorio_git.exists():
            return False

        self.diretorio_git.mkdir()
        self.diretorio_objetos.mkdir()
        self.diretorio_ref.mkdir()
        self.diretorio_heads.mkdir()

        # Cria o HEAD apontando para master (mesmo que master ainda não exista)
        self.arquivo_head.write_text("ref: refs/heads/master\n")
        
        # Cria um index vazio (JSON simples neste clone, binário complexo no Git real)
        self.salvar_index({})

        print(f"Repositório Git vazio inicializado em {self.diretorio_git}")
        return True

    def armazenar_objeto(self, objeto: ObjetoGit) -> str:
        """Escreve um objeto no disco (pasta objects) e retorna seu Hash."""
        hash_obj = objeto.calcular_hash()
        # O Git organiza objetos usando os 2 primeiros caracteres do hash como pasta
        # Ex: hash "a1b2c3..." fica em ".git/objects/a1/b2c3..."
        diretorio_obj = self.diretorio_objetos / hash_obj[:2]
        arquivo_obj = diretorio_obj / hash_obj[2:]

        if not arquivo_obj.exists():
            diretorio_obj.mkdir(exist_ok=True)
            arquivo_obj.write_bytes(objeto.serializar())

        return hash_obj

    # --- FUNÇÕES DE STAGING (ADD) ---

    def carregar_index(self) -> Dict[str, str]:
        """Carrega o Staging Area (arquivo 'index')."""
        if not self.arquivo_index.exists():
            return {}
        try:
            return json.loads(self.arquivo_index.read_text())
        except:
            return {}

    def salvar_index(self, index: Dict[str, str]):
        self.arquivo_index.write_text(json.dumps(index, indent=2))

    def adicionar_arquivo(self, caminho_arquivo: str):
        """
        Lógica do 'git add <arquivo>':
        1. Lê o conteúdo do arquivo.
        2. Cria um objeto BLOB.
        3. Salva o BLOB no banco de dados (.git/objects).
        4. Atualiza o INDEX mapeando 'caminho/do/arquivo' -> Hash do Blob.
        """
        caminho_completo = self.caminho_repo / caminho_arquivo
        if not caminho_completo.exists():
            raise FileNotFoundError(f"Caminho {caminho_arquivo} não encontrado")
        
        conteudo = caminho_completo.read_bytes()
        blob = Blob(conteudo)
        
        # O arquivo é salvo no banco de dados interno AGORA, não no commit
        hash_blob = self.armazenar_objeto(blob)
        
        index = self.carregar_index()
        index[caminho_arquivo] = hash_blob
        self.salvar_index(index)

        print(f"Adicionado {caminho_arquivo}")

    def adicionar_diretorio(self, caminho_diretorio: str):
        """Recursivamente adiciona arquivos de uma pasta."""
        caminho_completo = self.caminho_repo / caminho_diretorio
        if not caminho_completo.exists():
            raise FileNotFoundError(f"Diretório {caminho_diretorio} não encontrado")
        if not caminho_completo.is_dir():
            raise ValueError(f"{caminho_diretorio} não é um diretório")
        
        index = self.carregar_index()
        contador_adicionados = 0
        
        for caminho_arquivo in caminho_completo.rglob("*"):
            if caminho_arquivo.is_file():
                if "edugit" in caminho_arquivo.parts:
                    continue # Ignora a pasta edugit interna

                conteudo = caminho_arquivo.read_bytes()
                blob = Blob(conteudo)
                hash_blob = self.armazenar_objeto(blob)
                
                caminho_relativo = str(caminho_arquivo.relative_to(self.caminho_repo))
                index[caminho_relativo] = hash_blob
                contador_adicionados += 1

        self.salvar_index(index)
        if contador_adicionados > 0:
            print(f"Adicionado(s) {contador_adicionados} arquivo(s) do diretório {caminho_diretorio}")
        else:
            print(f"Diretório {caminho_diretorio} já está atualizado")

    def adicionar_caminho(self, caminho: str) -> None:
        """Roteador para adicionar arquivo ou diretório."""
        caminho_completo = self.caminho_repo / caminho
        if not caminho_completo.exists():
            raise FileNotFoundError(f"Caminho {caminho} não encontrado")

        if caminho_completo.is_file():
            self.adicionar_arquivo(caminho)
        elif caminho_completo.is_dir():
            self.adicionar_diretorio(caminho)
        else:
            raise ValueError(f"{caminho} não é um arquivo nem um diretório")

    def carregar_objeto(self, hash_obj: str) -> ObjetoGit:
        """Lê um objeto do disco dado seu Hash."""
        diretorio_obj = self.diretorio_objetos / hash_obj[:2]
        arquivo_obj = diretorio_obj / hash_obj[2:]

        if not arquivo_obj.exists():
            raise FileNotFoundError(f"Objeto {hash_obj} não encontrado")

        return ObjetoGit.desserializar(arquivo_obj.read_bytes())

    # --- CRIAÇÃO DE TREE E COMMIT ---

    def criar_arvore_do_index(self):
        """
        Converte o Index (lista plana de arquivos) em uma estrutura
        hierárquica de objetos Tree (diretórios).
        Isso é necessário antes de criar um Commit.
        """
        index = self.carregar_index()
        if not index:
            arvore = Arvore()
            return self.armazenar_objeto(arvore)

        diretorios = {}
        arquivos = {}

        # Organiza a lista plana em dicionários aninhados
        for caminho_arquivo, hash_blob in index.items():
            partes = caminho_arquivo.split("/")
            if len(partes) == 1:
                arquivos[partes[0]] = hash_blob
            else:
                nome_dir = partes[0]
                if nome_dir not in diretorios:
                    diretorios[nome_dir] = {}
                atual = diretorios[nome_dir]
                for parte in partes[1:-1]:
                    if parte not in atual:
                        atual[parte] = {}
                    atual = atual[parte]
                atual[partes[-1]] = hash_blob

        # Função recursiva para criar objetos Tree a partir dos dicionários
        def criar_arvore_recursiva(dicionario_entradas: Dict):
            arvore = Arvore()
            for nome, hash_blob in dicionario_entradas.items():
                if isinstance(hash_blob, str): # É um arquivo
                    arvore.adicionar_entrada("100644", nome, hash_blob)
                if isinstance(hash_blob, dict): # É uma subpasta
                    hash_subarvore = criar_arvore_recursiva(hash_blob)
                    arvore.adicionar_entrada("40000", nome, hash_subarvore)
            return self.armazenar_objeto(arvore)

        entradas_raiz = {**arquivos}
        for nome_dir, conteudo_dir in diretorios.items():
            entradas_raiz[nome_dir] = conteudo_dir

        return criar_arvore_recursiva(entradas_raiz)

    # --- GERENCIAMENTO DE BRANCHES ---

    def obter_branch_atual(self) -> str:
        """Lê o arquivo .git/HEAD para saber onde estamos."""
        if not self.arquivo_head.exists():
            return "master"
        conteudo_head = self.arquivo_head.read_text().strip()
        if conteudo_head.startswith("ref: refs/heads/"):
            return conteudo_head[16:]
        return "HEAD" 

    def obter_commit_branch(self, branch_atual: str):
        """Lê o Hash do commit apontado por um branch (em refs/heads/)."""
        arquivo_branch = self.diretorio_heads / branch_atual
        if arquivo_branch.exists():
            return arquivo_branch.read_text().strip()
        return None

    def definir_commit_branch(self, branch_atual: str, hash_commit: str):
        """Atualiza o ponteiro do branch para um novo commit."""
        arquivo_branch = self.diretorio_heads / branch_atual
        arquivo_branch.write_text(hash_commit + "\n")

    def commit(
        self,
        mensagem: str,
        autor: str = "Usuário PyGit <user@pygit.com>",
    ):
        """
        Cria um objeto Commit.
        1. Transforma Index em Trees.
        2. Pega o commit pai (do branch atual).
        3. Cria o objeto Commit apontando para a Tree e o Pai.
        4. Atualiza o ponteiro do Branch atual (HEAD) para este novo commit.
        """
        hash_arvore = self.criar_arvore_do_index()
        branch_atual = self.obter_branch_atual()
        commit_pai = self.obter_commit_branch(branch_atual)
        hashes_pai = [commit_pai] if commit_pai else []

        # Verifica se houve mudanças
        index = self.carregar_index()
        if not index:
            print("nada a ser commitado, a árvore de trabalho está limpa")
            return None
        if commit_pai:
            objeto_commit_pai = self.carregar_objeto(commit_pai)
            dados_commit_pai = Commit.a_partir_do_conteudo(objeto_commit_pai.conteudo)
            if hash_arvore == dados_commit_pai.hash_arvore:
                print("nada a ser commitado, a árvore de trabalho está limpa")
                return None

        commit = Commit(
            hash_arvore=hash_arvore,
            hashes_pai=hashes_pai,
            autor=autor,
            autor_commit=autor,
            mensagem=mensagem,
        )
        hash_commit = self.armazenar_objeto(commit)

        # Atualiza a referência do branch (Ex: refs/heads/master agora aponta para este commit)
        self.definir_commit_branch(branch_atual, hash_commit)
        
        # Limpa o index (opcional, dependendo da implementação do git, mas comum esvaziar)
        # Nota: Git real mantém o index, aqui estamos limpando por simplificação
        # ou o código original assume que index deve ser recriado.
        # No git real, o index vira o espelho do ultimo commit.
        # Mantendo o comportamento original do código:
        # self.save_index({}) 
        # (Obs: removi a limpeza forçada para manter lógica de 'staging' persistente se desejado,
        # mas o código original limpava. Mantenha se quiser limpar o palco após commit)
        
        print(f"Commit {hash_commit} criado no branch {branch_atual}")
        return hash_commit

    # ... (métodos auxiliares get_files_from_tree_recursive omitidos por brevidade) ...
    def obter_arquivos_da_arvore_recursivamente(self, hash_arvore: str, prefixo: str = ""):
        # Recupera recursivamente todos os arquivos de uma Tree para restauração
        arquivos = set()
        try:
            objeto_arvore = self.carregar_objeto(hash_arvore)
            arvore = Arvore.a_partir_do_conteudo(objeto_arvore.conteudo)
            for modo, nome, hash_obj in arvore.entradas:
                nome_completo = f"{prefixo}{nome}"
                if modo.startswith("100"): # Arquivo
                    arquivos.add(nome_completo)
                elif modo.startswith("400"): # Diretório
                    arquivos_subarvore = self.obter_arquivos_da_arvore_recursivamente(
                        hash_obj, f"{nome_completo}/"
                    )
                    arquivos.update(arquivos_subarvore)
        except Exception as e:
            print(f"Aviso: Não foi possível ler a árvore {hash_arvore}: {e}")
        return arquivos

    def checkout(self, nome_branch: str, criar_branch: bool):
        """
        Muda de branch e atualiza os arquivos no diretório de trabalho.
        """
        # --- Verificação de Segurança Adicionada ---
        # Verifica se há alterações no index que não estão no último commit
        index = self.carregar_index()
        if index and self.criar_arvore_do_index() != self.obter_hash_arvore_commit_atual():
            print("Erro: Suas alterações locais seriam sobrescritas pela migração.")
            print("Por favor, grave suas alterações ('gravar') ou reverta-as antes de migrar de ramo.")
            return

        branch_anterior = self.obter_branch_atual()
        arquivos_para_limpar = set()
        
        # Descobre quais arquivos existiam no branch antigo para removê-los se necessário
        try:
            hash_commit_anterior = self.obter_commit_branch(branch_anterior)
            if hash_commit_anterior:
                objeto_commit_anterior = self.carregar_objeto(hash_commit_anterior)
                commit_anterior = Commit.a_partir_do_conteudo(objeto_commit_anterior.conteudo)
                if commit_anterior.hash_arvore:
                    arquivos_para_limpar = self.obter_arquivos_da_arvore_recursivamente(commit_anterior.hash_arvore)
        except Exception:
            arquivos_para_limpar = set()

        arquivo_branch = self.diretorio_heads / nome_branch
        
        # Lógica de criar branch novo (-b)
        if not arquivo_branch.exists():
            if criar_branch:
                if hash_commit_anterior:
                    # Cria o arquivo refs/heads/<novo_branch> apontando para o commit atual
                    self.definir_commit_branch(nome_branch, hash_commit_anterior)
                    print(f"Novo branch {nome_branch} criado")
                else:
                    print("Ainda não há commits, não é possível criar um branch")
                    return
            else:
                print(f"Branch '{nome_branch}' não encontrado.")
                return
        
        # Atualiza o HEAD para apontar para o novo branch
        self.arquivo_head.write_text(f"ref: refs/heads/{nome_branch}\n")

        # Restaura os arquivos físicos no diretório
        self.restaurar_diretorio_trabalho(nome_branch, arquivos_para_limpar)
        print(f"Alternado para o branch {nome_branch}")

    def restaurar_arvore(self, hash_arvore: str, caminho: Path):
        """Reconstrói fisicamente os arquivos a partir de uma Tree."""
        objeto_arvore = self.carregar_objeto(hash_arvore)
        arvore = Arvore.a_partir_do_conteudo(objeto_arvore.conteudo)
        for modo, nome, hash_obj in arvore.entradas:
            caminho_arquivo = caminho / nome
            if modo.startswith("100"): # Blob
                objeto_blob = self.carregar_objeto(hash_obj)
                blob = Blob(objeto_blob.conteudo)
                caminho_arquivo.write_bytes(blob.conteudo)
            elif modo.startswith("400"): # Tree
                caminho_arquivo.mkdir(exist_ok=True)
                self.restaurar_arvore(hash_obj, caminho_arquivo)

    def restaurar_diretorio_trabalho(self, nome_branch: str, arquivos_para_limpar: set[str]):
        """Limpa arquivos antigos e escreve os novos."""
        hash_commit_alvo = self.obter_commit_branch(nome_branch)
        if not hash_commit_alvo:
            return

        # Apaga arquivos do branch anterior
        for caminho_relativo in sorted(arquivos_para_limpar):
            caminho_arquivo = self.caminho_repo / caminho_relativo
            try:
                if caminho_arquivo.is_file():
                    caminho_arquivo.unlink()
            except Exception:
                pass

        # Escreve arquivos do novo branch
        objeto_commit_alvo = self.carregar_objeto(hash_commit_alvo)
        commit_alvo = Commit.a_partir_do_conteudo(objeto_commit_alvo.conteudo)
        if commit_alvo.hash_arvore:
            self.restaurar_arvore(commit_alvo.hash_arvore, self.caminho_repo)
            
        # Reseta o index para bater com o novo commit
        self.salvar_index({})

    def branch(self, nome_branch: str, deletar: bool = False):
        """Lista, cria ou deleta branches."""
        # Deletar (-d)
        if deletar and nome_branch:
            arquivo_branch = self.diretorio_heads / nome_branch
            if arquivo_branch.exists():
                arquivo_branch.unlink() # Apenas apaga o arquivo em refs/heads/
                print(f"Branch {nome_branch} deletado")
            else:
                print(f"Branch {nome_branch} não encontrado")
            return

        branch_atual = self.obter_branch_atual()
        
        # Criar (se passar nome)
        if nome_branch:
            commit_atual = self.obter_commit_branch(branch_atual)
            if commit_atual:
                self.definir_commit_branch(nome_branch, commit_atual)
                print(f"Branch {nome_branch} criado")
            else:
                print(f"Ainda não há commits, não é possível criar um novo branch")
        # Listar (se não passar nome)
        else:
            branches = []
            for arquivo_branch in self.diretorio_heads.iterdir():
                if arquivo_branch.is_file() and not arquivo_branch.name.startswith("."):
                    branches.append(arquivo_branch.name)

            for branch in sorted(branches):
                marcador_atual = "* " if branch == branch_atual else "  "
                print(f"{marcador_atual}{branch}")

    def log(self, maximo_commits: int = 10):
        """Mostra o histórico navegando pelos hashes 'parent'."""
        branch_atual = self.obter_branch_atual()
        hash_commit = self.obter_commit_branch(branch_atual)

        if not hash_commit:
            print("Ainda não há commits!")
            return

        contador = 0
        while hash_commit and contador < maximo_commits:
            objeto_commit = self.carregar_objeto(hash_commit)
            commit = Commit.a_partir_do_conteudo(objeto_commit.conteudo)

            print(f"commit {hash_commit}")
            print(f"Autor: {commit.autor}")
            print(f"Data: {time.ctime(commit.timestamp)}")
            print(f"\n    {commit.mensagem}\n")

            # Pega o primeiro pai para continuar o loop para trás
            hash_commit = commit.hashes_pai[0] if commit.hashes_pai else None
            contador += 1

    def obter_hash_arvore_commit_atual(self) -> str | None:
        """Função auxiliar para pegar o hash da árvore do commit atual."""
        branch_atual = self.obter_branch_atual()
        hash_commit_atual = self.obter_commit_branch(branch_atual)
        if not hash_commit_atual:
            return None
        
        objeto_commit = self.carregar_objeto(hash_commit_atual)
        commit = Commit.a_partir_do_conteudo(objeto_commit.conteudo)
        return commit.hash_arvore


    def obter_tipo_objeto(self, hash_obj: str) -> str:
        """Lê um objeto e retorna seu tipo (blob, tree, ou commit) sem desserializar o objeto inteiro."""
        diretorio_obj = self.diretorio_objetos / hash_obj[:2]
        arquivo_obj = diretorio_obj / hash_obj[2:]

        if not arquivo_obj.exists():
            raise FileNotFoundError(f"Objeto {hash_obj} não encontrado")

        dados_comprimidos = arquivo_obj.read_bytes()
        dados_descomprimidos = zlib.decompress(dados_comprimidos)
        
        indice_nulo = dados_descomprimidos.find(b'\0')
        cabecalho = dados_descomprimidos[:indice_nulo].decode()
        
        tipo_obj, _ = cabecalho.split(' ', 1)
        return tipo_obj

    # ... (métodos auxiliares build_index_from_tree, get_all_files, status mantidos iguais) ...
    # Para brevidade, mantive o restante do código sem alterações profundas de comentários 
    # pois a lógica principal (Init, Add, Commit, Branch) já foi coberta acima.
    
    def construir_index_da_arvore(self, hash_arvore: str, prefixo: str = ""):
        index = {}
        try:
            objeto_arvore = self.carregar_objeto(hash_arvore)
            arvore = Arvore.a_partir_do_conteudo(objeto_arvore.conteudo)
            for modo, nome, hash_obj in arvore.entradas:
                nome_completo = f"{prefixo}{nome}"
                if modo.startswith("100"):
                    index[nome_completo] = hash_obj
                elif modo.startswith("400"):
                    subindex = self.construir_index_da_arvore(hash_obj, f"{nome_completo}/")
                    index.update(subindex)
        except Exception as e:
            print(f"Aviso: Não foi possível ler a árvore {hash_arvore}: {e}")
        return index

    def obter_todos_arquivos(self) -> List[Path]:
        arquivos = []
        for item in self.caminho_repo.rglob("*"):
            if "edugit" in item.parts:
                continue
            if item.is_file():
                arquivos.append(item)
        return arquivos

    def status(self):
        branch_atual = self.obter_branch_atual()
        print(f"No branch {branch_atual}")
        index = self.carregar_index()
        hash_commit_atual = self.obter_commit_branch(branch_atual)

        arquivos_ultimo_index = {}
        if hash_commit_atual:
            try:
                objeto_commit = self.carregar_objeto(hash_commit_atual)
                commit = Commit.a_partir_do_conteudo(objeto_commit.conteudo)
                if commit.hash_arvore:
                    arquivos_ultimo_index = self.construir_index_da_arvore(commit.hash_arvore)
            except:
                arquivos_ultimo_index = {}

        arquivos_trabalho = {} 
        for item in self.obter_todos_arquivos():
            caminho_relativo = str(item.relative_to(self.caminho_repo))
            try:
                conteudo = item.read_bytes()
                blob = Blob(conteudo)
                arquivos_trabalho[caminho_relativo] = blob.calcular_hash()
            except:
                continue

        arquivos_em_staging = []
        arquivos_nao_em_staging = []
        arquivos_nao_rastreados = []
        arquivos_deletados = []

        for caminho_arquivo in set(index.keys()) | set(arquivos_ultimo_index.keys()):
            hash_index = index.get(caminho_arquivo)
            hash_ultimo_index = arquivos_ultimo_index.get(caminho_arquivo)

            if hash_index and not hash_ultimo_index:
                arquivos_em_staging.append(("novo arquivo", caminho_arquivo))
            elif hash_index and hash_ultimo_index and hash_index != hash_ultimo_index:
                arquivos_em_staging.append(("modificado", caminho_arquivo))

        if arquivos_em_staging:
            print("\nAlterações a serem commitadas:")
            for status_staging, caminho_arquivo in sorted(arquivos_em_staging):
                print(f"   {status_staging}: {caminho_arquivo}")

        for caminho_arquivo in arquivos_trabalho:
            if caminho_arquivo in index:
                if arquivos_trabalho[caminho_arquivo] != index[caminho_arquivo]:
                    arquivos_nao_em_staging.append(caminho_arquivo)

        if arquivos_nao_em_staging:
            print("\nAlterações não preparadas para commit:")
            for caminho_arquivo in sorted(arquivos_nao_em_staging):
                print(f"   modificado: {caminho_arquivo}")

        for caminho_arquivo in arquivos_trabalho:
            if caminho_arquivo not in index and caminho_arquivo not in arquivos_ultimo_index:
                arquivos_nao_rastreados.append(caminho_arquivo)

        if arquivos_nao_rastreados:
            print("\nArquivos não rastreados:")
            for caminho_arquivo in sorted(arquivos_nao_rastreados):
                print(f"   {caminho_arquivo}")

        for caminho_arquivo in index:
            if caminho_arquivo not in arquivos_trabalho:
                arquivos_deletados.append(caminho_arquivo)

        if arquivos_deletados:
            print("\nArquivos deletados:")
            for caminho_arquivo in sorted(arquivos_deletados):
                print(f"   deletado: {caminho_arquivo}")

        if (not arquivos_em_staging and not arquivos_nao_em_staging and not arquivos_deletados and not arquivos_nao_rastreados):
            print("\nnada a ser commitado, a árvore de trabalho está limpa")

# --- INTERFACE DE LINHA DE COMANDO (CLI) ---

def main():
    parser = argparse.ArgumentParser(description="PyGit - Um clone simples do git!")
    subparsers = parser.add_subparsers(dest="comando", help="Comandos disponíveis")

    init_parser = subparsers.add_parser("iniciar", help="Inicializa um novo repositório")

    add_parser = subparsers.add_parser(
        "adicionar", help="Adiciona arquivos e diretórios para a área de staging"
    )
    add_parser.add_argument("caminhos", nargs="+", help="Arquivos e diretórios a adicionar")

    commit_parser = subparsers.add_parser("gravar", help="Cria um novo commit (grava as alterações)")
    commit_parser.add_argument(
        "-m", "--mensagem", help="Mensagem do commit", required=True,
    )
    commit_parser.add_argument("--autor", help="Nome e email do autor")

    checkout_parser = subparsers.add_parser("migrar", help="Muda para outro ramo (branch) ou cria um novo")
    checkout_parser.add_argument("branch", help="Branch para o qual alternar")
    checkout_parser.add_argument(
        "-b", "--criar-branch", action="store_true", help="Cria e alterna para um novo branch",
    )

    branch_parser = subparsers.add_parser("ramo", help="Lista, cria ou deleta ramos (branches)")
    branch_parser.add_argument("nome", nargs="?")
    branch_parser.add_argument(
        "-d", "--deletar", action="store_true", help="Deleta o branch",
    )

    log_parser = subparsers.add_parser("historico", help="Mostra o histórico de commits")
    log_parser.add_argument(
        "-n", "--maximo-commits", type=int, default=10, help="Limita o número de commits mostrados",
    )

    status_parser = subparsers.add_parser("estado", help="Mostra o estado do repositório (status)")

    tipo_parser = subparsers.add_parser("tipo-objeto", help="Mostra o tipo de um objeto a partir do seu hash")
    tipo_parser.add_argument("hash", help="O hash SHA-1 do objeto")

    args = parser.parse_args()

    if not args.comando:
        parser.print_help()
        return

    repo = Repositorio()
    try:
        if args.comando == "iniciar":
            if not repo.init():
                print("O repositório já existe")
                return
        elif args.comando == "adicionar":
            if not repo.diretorio_git.exists():
                print("Não é um repositório git")
                return
            for caminho in args.caminhos:
                repo.adicionar_caminho(caminho)
        elif args.comando == "gravar":
            if not repo.diretorio_git.exists():
                print("Não é um repositório git")
                return
            autor = args.autor or "Usuário PyGit <user@pygit.com>"
            repo.commit(args.mensagem, autor)
        elif args.comando == "migrar":
            if not repo.diretorio_git.exists():
                print("Não é um repositório git")
                return
            repo.checkout(args.branch, args.criar_branch)
        elif args.comando == "ramo":
            if not repo.diretorio_git.exists():
                print("Não é um repositório git")
                return
            repo.branch(args.nome, args.deletar)
        elif args.comando == "historico":
            if not repo.diretorio_git.exists():
                print("Não é um repositório git")
                return
            repo.log(args.maximo_commits)
        elif args.comando == "estado":
            if not repo.diretorio_git.exists():
                print("Não é um repositório git")
                return
            repo.status()
        elif args.comando == "tipo-objeto":
            if not repo.diretorio_git.exists():
                print("Não é um repositório git")
                return
            tipo = repo.obter_tipo_objeto(args.hash)
            print(tipo)

    except Exception as e:
        print(f"Erro: {e}")
        sys.exit(1)

main()
