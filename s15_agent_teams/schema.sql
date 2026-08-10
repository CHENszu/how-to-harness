-- =============================================
-- Database Schema for E-Commerce Application
-- =============================================

-- --------------------------------------------------
-- Users table: stores customer & admin accounts
-- --------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    email         VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    first_name    VARCHAR(50),
    last_name     VARCHAR(50),
    phone         VARCHAR(20),
    role          ENUM('customer', 'admin') DEFAULT 'customer',
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------
-- Addresses table: shipping/billing addresses per user
-- --------------------------------------------------
CREATE TABLE IF NOT EXISTS addresses (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    user_id      INT NOT NULL,
    street       VARCHAR(255) NOT NULL,
    city         VARCHAR(100) NOT NULL,
    state        VARCHAR(100),
    postal_code  VARCHAR(20),
    country      VARCHAR(100) NOT NULL DEFAULT 'CN',
    is_default   BOOLEAN DEFAULT FALSE,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------
-- Categories table: product categories
-- --------------------------------------------------
CREATE TABLE IF NOT EXISTS categories (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    parent_id   INT DEFAULT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES categories(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------
-- Products table: store products
-- --------------------------------------------------
CREATE TABLE IF NOT EXISTS products (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    category_id  INT,
    name         VARCHAR(255) NOT NULL,
    description  TEXT,
    price        DECIMAL(10, 2) NOT NULL,
    stock        INT NOT NULL DEFAULT 0,
    sku          VARCHAR(50) UNIQUE,
    image_url    VARCHAR(500),
    is_active    BOOLEAN DEFAULT TRUE,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------
-- Orders table: order headers
-- --------------------------------------------------
CREATE TABLE IF NOT EXISTS orders (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    user_id            INT NOT NULL,
    address_id         INT,
    order_number       VARCHAR(40) NOT NULL UNIQUE,
    status             ENUM('pending', 'paid', 'shipped', 'delivered', 'cancelled')
                       DEFAULT 'pending',
    subtotal           DECIMAL(10, 2) NOT NULL,
    shipping_fee       DECIMAL(10, 2) DEFAULT 0.00,
    tax                DECIMAL(10, 2) DEFAULT 0.00,
    total              DECIMAL(10, 2) NOT NULL,
    payment_method     VARCHAR(50),
    paid_at            DATETIME,
    shipped_at         DATETIME,
    delivered_at       DATETIME,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (address_id) REFERENCES addresses(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------
-- Order_Items table: line items for each order
-- --------------------------------------------------
CREATE TABLE IF NOT EXISTS order_items (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    order_id    INT NOT NULL,
    product_id  INT NOT NULL,
    quantity    INT NOT NULL,
    unit_price  DECIMAL(10, 2) NOT NULL,
    subtotal    DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (order_id)  REFERENCES orders(id)  ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------
-- Payments table: payment records for orders
-- --------------------------------------------------
CREATE TABLE IF NOT EXISTS payments (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    order_id       INT NOT NULL,
    amount         DECIMAL(10, 2) NOT NULL,
    method         VARCHAR(50) NOT NULL,
    transaction_id VARCHAR(100),
    status         ENUM('pending', 'success', 'failed') DEFAULT 'pending',
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =============================================
-- Indexes for query performance
-- =============================================
CREATE INDEX idx_users_email        ON users(email);
CREATE INDEX idx_orders_user_id     ON orders(user_id);
CREATE INDEX idx_orders_status      ON orders(status);
CREATE INDEX idx_products_category  ON products(category_id);
CREATE INDEX idx_order_items_order  ON order_items(order_id);
CREATE INDEX idx_addresses_user_id  ON addresses(user_id);
