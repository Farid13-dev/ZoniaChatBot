// El token va en el bundle: cualquiera que abra el sitio puede leerlo. Es
// aceptable en un prototipo local, NO en produccion (ver README, Limitaciones
// conocidas). Debe coincidir con ADMIN_TOKEN del .env del backend; si se deja
// vacio, los endpoints de administracion responden 403.
export const environment = {
  production: false,
  adminToken: ''
};
