# Network Configuration Normalizer

Antes de ejecutar el script deberan crear dos carpetas en la raiz de este projecto:

- **backup_configuration**
- **input_information**

Quedando la estructura de archivos de la siguiente manera:

```
-|
 |- backup_configuration/
 |- input_information/
 |- .gitignore
 |- device_factory.py
 |- device_models.py
 |- run_script.py
 |- transition_device.py
```

En la carpeta "input_information" deberan guardar un archivo CSV con el nombre "data.csv" que contenga la informacion de los equipos y puertos que deberan ser modificados con este script. El encabezado del csv sera: device_model_id, mgmt_ip, port_number. Por ejemplo:

```
device_model_id,mgmt_ip,port_number
1,1.1.1.1,13
1,1.1.1.1,14
2,2.2.2.2,6
2,2.2.2.2,7
```

- **device_model_id:** ID del modelo del equipo. Deberan utilizar "1" para el modelo 4224 y "3" para el LIB4424.
- **mgmt_ip:** IP de gestion del equipo.
- **port_number:** Puerto del equipo que desean normalizar. Solo deberan colocar el numero del puerto, por ejemplo el puerto "GigabitEthernet 1/2" tiene como numero de puerto el numero "2".

En la carpeta "backup_configuration" se guarda la configuracion del equipo en texto plano y una version de la configuracion y datos operativos (tabla de mac-address, DDMi, etc) en json. Estos archivos representan el estado del equipo antes de aplicar cualquier cambio.