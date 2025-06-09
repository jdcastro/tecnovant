# TecnoAgro

Sistema de Gestión de Nutrición Foliar en Cultivos

## 1. Introducción

<pre>En este documento se describe la estructura y las relaciones de la base de datos 
diseñada para un proyecto base de Flask con modularidad y control de 
acceso. La base de datos está diseñada para soportar la gestión de usuarios proporcionando
una base sólida para el desarrollo de funcionales adicionales escalables y seguras.

Este modelo SQLAlchemy implementa un sistema de control de acceso basado en roles y permisos, diseñado para gestionar usuarios, sus roles, permisos y acciones asociadas dentro de un esquema de reseller. Incluye también modelos para clientes, límites para reseller y módulos del sistema.

Gestión de permisos:

El modelo de roles, acciones y permisos es manejado de manera estática con enumeraciones
La definición de roles, acciones y permisos se hace mediante enums para que la estructura sea muy clara y fácil de mantener.

Los cambios en los permisos o roles se pueden gestionar de manera centralizada en los enums y diccionarios asociados.
</pre>

### **Descripción del Software: TecnoAgro**  

El proyecto TecnoAgro consiste en un sistema de software para la gestión de datos relacionados con la nutrición foliar en cultivos diseñado para ayudar a los agricultores a optimizar el uso de nutrientes y mejorar la producción. Cómo insumo se ingresan los datos obtenidos a partir de imágenes de drones procesadas externamente y complementadas con información ingresada manualmente. 

El sistema recibe estos datos a través de una API y un formulario de ingreso, los analiza y los almacena para generar recomendaciones personalizadas basadas en parámetros locales de nutrientes. Su enfoque permite una toma de decisiones precisa, mejorando la eficiencia en el uso de recursos y la productividad agrícola.

Entre las tecnologías seleccionadas están MariaDB/MySQL, Flask, Flask-SQLAlchemy, Jinja2 templates, blueprint, Flask-JWT-Extended para login y api.

## 2. Arquitectura del Software

La arquitectura del sistema se basa en un diseño modular y escalable, utilizando el patrón MVC (Modelo-Vista-Controlador) con una arquitectura RESTful para separar la lógica de negocio, la presentación y el acceso a datos. 

### Modelo (Model)
Base de datos : Se utiliza **Flask-SQLAlchemy** para interactuar con la base de datos MySQL. Las tablas y relaciones se definen como clases Python, siguiendo el patrón de Active Record.

**Migraciones** : Flask-Migrate se usa para gestionar cambios en el esquema de la base de datos (creación, actualización, etc.).

### Vista (View)

**Templating**
- **Jinja2** se utiliza para generar HTML dinámico. Las plantillas están organizadas de forma modular, reutilizando componentes comunes como headers y footers para mantener la consistencia y facilitar el mantenimiento.

**Frontend**
- **Tailwind CSS** se integra para estilizar la interfaz, proporcionando un diseño responsivo y moderno.
- **JavaScript** interactúa con los endpoints de la API, permitiendo una experiencia de usuario dinámica y fluida.

###  Controlador (Controller)

- **Rutas:** Se definen en archivos separados utilizando **Blueprints** de Flask. Esto modulariza la aplicación, promoviendo un código limpio y organizado.
- **Lógica de negocio:** Se maneja en funciones independientes, asegurando la separación de responsabilidades siguiendo los principios SOLID.

**Seguridad** y **Validaciones**
   - **Werkzeug**: Implementación segura de hash de contraseñas.
   - **Marshmallow**: Librería para serialización y validación de datos, garantizando la integridad de los datos antes de su almacenamiento.

### Manejo de APIs
- **Endpoints:** Se implementan como rutas específicas en Flask, devolviendo respuestas en formato JSON para ser consumidas por clientes como el frontend web o aplicaciones móviles.
- **Autenticación:** Se utiliza **flask-jwt-extended** para gestionar la autenticación basada en tokens, garantizando un acceso seguro a los recursos protegidos. Se Implementa JWT (JSON Web Tokens) para autenticación de usuarios. Gestiona tokens de acceso y actualización, con funcionalidades como:
     - Login
     - Logout
     - Refresh token
     - Protección de rutas con `@jwt_required()`


La estructura del proyecto sigue patrones de diseño modernos, con módulos separados para:
- Modelos de datos (`model.py`)
- Rutas y vistas (`routes.py`)
- Endpoints  (`api_routes.py`)
- Funcionalidades auxiliares (`controller.py`)

El código incluye manejadores de errores, logging y excepciones, asegurando una buena practica para la depuración y monitoreo.
Se utiliza el Micro framework **Flask**  para desarrollar aplicación web en Python y Blueprints para modularizar la aplicación.

CREAR: DIAGRAMA mermaid de relación web - api 

### Resumen de Componentes Clave
**Templating**: Jinja2 organiza plantillas de forma modular.
**Frontend**: Utiliza Tailwind CSS para estilos y JavaScript para interacciones dinámicas con la API.
**Controladores**: Gestionados mediante Blueprints para modularizar rutas.
**Lógica de Negocio**: Separada en funciones independientes siguiendo principios SOLID.
**Manejo de APIs**: Endpoints REST seguros con autenticación basada en tokens mediante flask-jwt-extended.

## 3. Requisitos de la herramienta

#### Requisitos Funcionales

1. Gestión de usuarios y autenticación
	- Creación de usuario admin.
	- Inicio de sesión
	- Registro de usuarios y asociación a fincas
	- Gestión de permisos por usuario y finca
2. Ingreso de datos
	- Formulario para ingreso manual de datos
		- ***A futuro***: Integración con API externa para recepción de datos procesados de imágenes de drones
		- Importación y exportación de datos a CSV
3. Análisis y almacenamiento de datos
	- Procesamiento de datos recibidos
	- Almacenamiento en la base de datos
4. Generación de recomendaciones
	- Análisis de datos almacenados
	- Generación de recomendaciones personalizadas basadas en parámetros locales de nutrientes
5. Reportes y visualizaciones
	- Generación de reportes de estado
	- Creación de gráficas de seguimiento
	- Generación de pronósticos
	- Análisis de antagonismo entre nutrientes
6. Gestión de fincas y lotes
	- Creación y edición de fincas
	- Gestión de lotes por finca
7. Gestión de productos y precios
	- Mantenimiento de catálogo de productos
	- Actualización de precios

#### Requisitos No Funcionales

1. Seguridad
	1. Implementación de autenticación JWT
	2. Encriptación de datos sensibles
	3. Protección contra ataques comunes (SQL injection, XSS, CSRF)
2. Rendimiento
	1. Tiempo de respuesta menor a 2 segundos para operaciones comunes
	2. Capacidad para manejar al menos 1000 usuarios concurrentes
3. Escalabilidad
	1. Diseño modular que permita la fácil adición de nuevas funcionalidades
	2. Capacidad de escalar horizontalmente
4. Usabilidad
	1. Interfaz de usuario intuitiva y responsiva
	2. Compatibilidad con navegadores modernos
5. Mantenibilidad
	1. Código bien documentado y siguiendo estándares de codificación
	2. Uso de patrones de diseño para facilitar futuras modificaciones
6. Disponibilidad
	1. Tiempo de actividad del sistema de al menos 99.9%
7. Interoperabilidad
	1. ***A futuro:*** Integración fluida con la API externa de procesamiento de imágenes
	2. Capacidad para exportar datos en formatos estándar (CSV, JSON)

## 4. Diseño de la Base de Datos

El diseño de la base de datos se ha normalizado y optimizado para asegurar la eficiencia en la gestión de datos y evitar redundancias. Se han agregado tablas adicionales para manejar las relaciones entre usuarios, fincas y lotes.


### 1. **Modelo de permisos**

Se utiliza un diseño de "Permissions Based Access Control" (PBAC), que es muy flexible y escalable. 

---------------------

### Resumen del Modelo de Datos
1. **User**: Representa los usuarios del sistema.
2. **Role**: Los roles asignados a los usuarios.
3. **Permission**: Los permisos asociados a los roles.
4. **Action**: Las acciones que los permisos pueden realizar.
5. **Client**: Organizaciones que los usuarios pueden manejar.
6. **Module**: Módulos del sistema que los usuarios pueden acceder.
7. **ModulePermission**: Relación entre módulos y permisos.

### Diagrama de la Base de Datos de usuarios
CREAR: DIAGRAMA MERMAID de la DB
CREAR: Diagrama de la Secuencia de Pasos, Permisos y Restricciones
