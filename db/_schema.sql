SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

-- -------------------------------------------------

CREATE DATABASE IF NOT EXISTS edugit_db
	CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
    
USE edugit_db;

-- -------------------------------------------------
-- Tabela: usuarios
-- Descrição: armazena informações dos alunos e professores
-- -------------------------------------------------
CREATE TABLE IF NOT EXISTS usuarios (
		id INT AUTO_INCREMENT,
        matricula VARCHAR(25) NOT NULL PRIMARY KEY,
        nome VARCHAR(255) NOT NULL,
        email VARCHAR(255) NOT NULL UNIQUE,
        senha_hash VARCHAR(255) NOT NULL,
        tipo_usuario ENUM('aluno', 'professor') NOT NULL DEFAULT 'aluno',
        email_validado BOOLEAN DEFAULT false,
        `status` ENUM('ativo', 'inativo', 'suspenso') DEFAULT 'ativo',
        data_cadastro DATETIME NOT NULL DEFAULT current_timestamp
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

