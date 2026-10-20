/**
 * Crea en Google Forms el formulario "Retroalimentación del Termómetro
 * Institucional" de la fase de prueba con académicos.
 *
 * POR QUÉ EXISTE ESTE SCRIPT
 * El formulario ya vive dentro de la Torre (backend/app/services/formularios.py
 * y frontend/src/lib/formularios.ts, clave `retroalimentacion-termometro`), pero
 * esa versión está en la rama de integración, que va 699 commits detrás de main:
 * hasta que se porte y se despliegue no existe en ninguna parte que un académico
 * pueda abrir. Este script permite arrancar la fase de prueba hoy, mandando un
 * link por correo, sin esperar ese port.
 *
 * ES UN ESPEJO, NO UNA VERSIÓN NUEVA. Las 15 preguntas, su orden, su
 * obligatoriedad y la condicional son las mismas que las de la Torre. Si cambian
 * allá, cambian acá. Dos decisiones de orden que NO son estéticas y no se deben
 * "arreglar" al mirarlo:
 *   1. `que_mide` va ANTES de la lista de pestañas. Esa pregunta mide qué
 *      entendió la persona sin pistas, y enumerar las pestañas con sus nombres
 *      es darle la respuesta.
 *   2. "¿Entendiste el número?" y "¿Le crees al número?" son DOS preguntas.
 *      Se puede entender perfecto y no creerle, y es lo segundo lo que decide
 *      si alguien lo usa.
 *
 * CÓMO SE USA
 *   1. script.google.com → Nuevo proyecto → pegar este archivo.
 *   2. Ejecutar `crearFormulario`. La primera vez pide autorización (crea un
 *      formulario y una planilla en tu Drive).
 *   3. El log (Ver → Registro de ejecución) imprime el link para compartir y el
 *      link de edición. El de compartir es el que va en el correo a los
 *      académicos y en la variable NEXT_PUBLIC_PERCEPCION_FEEDBACK_URL del
 *      frontend, para que el botón del panel lleve acá.
 *
 * OJO: cada ejecución crea un formulario NUEVO y vacío. No actualiza el
 * anterior. Si ya hay respuestas, no lo vuelvas a correr: editá el formulario
 * existente desde su link de edición.
 */

/** Título del formulario y de la planilla de respuestas. */
var TITULO = 'Retroalimentación del Termómetro Institucional';

/**
 * Mismo texto que el `objective` de la definición de la Torre.
 * Desarma la ansiedad de quien responde: lo que no se entiende es un problema
 * del panel, no de quien lo lee. Sin esa frase la gente contesta lo que cree que
 * se espera de ella, y ahí el formulario deja de medir nada.
 */
var DESCRIPCION = [
  'Saber si el Termómetro se entiende y sirve para alguien fuera del equipo DAI.',
  'Toma unos 8 minutos y no hay respuestas correctas: lo que no se entiende es',
  'problema del panel, no de quien lo lee.',
].join(' ');

var ESCALA_MIN = 'Nada';
var ESCALA_MAX = 'Completamente';

function crearFormulario() {
  var form = FormApp.create(TITULO);
  form.setDescription(DESCRIPCION);
  form.setProgressBar(true);
  // Se permite responder más de una vez: alguien puede mirar el panel hoy y
  // volver a mirarlo con otros ojos la semana que viene, y las dos respuestas
  // sirven.
  form.setLimitOneResponsePerUser(false);
  _recolectarCorreo(form);

  // ---- Sección 1: todo lo que no depende de una respuesta previa ----

  form.addTextItem()
    .setTitle('Unidad o carrera a la que perteneces')
    .setRequired(true);

  _siNo(form, '¿Es la primera vez que ves el Termómetro Institucional?',
        'Si ya lo conocías, tu mirada sobre lo confuso es distinta y conviene separarla.',
        true);

  form.addParagraphTextItem()
    .setTitle('Con tus palabras: ¿qué crees que mide este panel?')
    .setHelpText('La pregunta más importante del formulario. No busques la respuesta ' +
                 'correcta ni revises antes: escribe lo que entendiste al mirarlo.')
    .setRequired(true);

  // Va DESPUÉS de `que_mide` a propósito (ver cabecera).
  form.addCheckboxItem()
    .setTitle('¿En cuáles de las pestañas alcanzaste a entrar?')
    .setHelpText('Si solo lo miraste por encima, déjalo vacío: eso también es un dato.')
    .setChoiceValues(['Resumen', 'Alertas', 'Comparar', 'Conversación']);

  _escala(form, '¿Pudiste entender qué significa el número principal, sin que nadie te explicara?', '');

  _escala(form, '¿Cuánto le crees al número que muestra?',
          'Distinto de si se entiende. Se puede entender perfecto y aun así no creerle, ' +
          'y eso también sirve saberlo.');

  form.addParagraphTextItem()
    .setTitle('¿Qué te resultó confuso, ambiguo o difícil de interpretar?')
    .setHelpText('Nombres de pestañas, palabras del panel, gráficos, números sin contexto.');

  _escala(form, '¿Qué tan útil te resulta esta información para tu trabajo?', '');

  form.addParagraphTextItem()
    .setTitle('¿Se te ocurre alguna decisión o conversación concreta en la que usarías esto?')
    .setHelpText('Si la respuesta es «ninguna», escríbelo: es un resultado válido y nos ' +
                 'dice más que un elogio.');

  form.addParagraphTextItem()
    .setTitle('¿Qué le falta para que te sirva más?');

  // Se crea ahora pero sus opciones se definen más abajo: para ramificar hay que
  // apuntar a secciones que todavía no existen.
  var cifraSospechosa = form.addMultipleChoiceItem()
    .setTitle('¿Viste alguna cifra que te pareciera equivocada o que no calce con lo que conoces?')
    .setRequired(true);

  // ---- Sección 2: solo si dijo que sí ----

  var seccionDetalle = form.addPageBreakItem()
    .setTitle('Sobre esa cifra');

  form.addParagraphTextItem()
    .setTitle('¿Cuál, y por qué te llamó la atención?')
    .setRequired(true);

  // ---- Sección 3: cierre, para todos ----

  var seccionCierre = form.addPageBreakItem()
    .setTitle('Para terminar');

  form.addParagraphTextItem()
    .setTitle('¿Hay algo de este panel que te genere reparos o dudas sobre cómo podría usarse?')
    .setHelpText('Se pregunta en serio, y ahora, que es cuando todavía se puede cambiar algo. ' +
                 'Si no tienes ninguno, déjalo vacío.');

  form.addParagraphTextItem()
    .setTitle('Cualquier otro comentario');

  _siNo(form, '¿Podemos escribirte para conversar unos minutos sobre lo que respondiste?',
        'Un «No» no le quita ningún valor a lo que acabas de escribir.',
        true);

  // ---- Ramificación ----
  // «Sí» entra al detalle; «No» lo saltea y cae directo en el cierre. Sin esto,
  // Forms le muestra la pregunta del detalle a todo el mundo, incluido quien
  // acaba de decir que no vio ninguna cifra rara.
  cifraSospechosa.setChoices([
    cifraSospechosa.createChoice('Sí', seccionDetalle),
    cifraSospechosa.createChoice('No', seccionCierre),
  ]);
  // Terminado el detalle, sigue al cierre (y no al final del formulario).
  seccionDetalle.setGoToPage(seccionCierre);

  var planilla = _vincularPlanilla(form);

  Logger.log('Formulario creado.');
  Logger.log('  Para compartir : ' + form.getPublishedUrl());
  Logger.log('  Para editar    : ' + form.getEditUrl());
  Logger.log('  Respuestas     : ' + planilla);
  return form.getPublishedUrl();
}

// ── Auxiliares ────────────────────────────────────────────────────────────────

/**
 * Pide el correo institucional de quien responde.
 *
 * Es lo que reemplaza a la sesión: dentro de la Torre el correo y la unidad
 * vienen del login, y acá no hay login. Sin correo, un «sí, escríbanme» no tiene
 * a quién escribirle.
 *
 * `setEmailCollectionType` es la API vigente; `setCollectEmail` es la anterior y
 * sigue viva en proyectos ya creados. Se intenta la nueva y se cae a la vieja en
 * vez de asumir cuál tiene la cuenta: si fallara, el formulario quedaría creado
 * pero anónimo, y eso no se nota hasta que llegan las respuestas.
 */
function _recolectarCorreo(form) {
  try {
    form.setEmailCollectionType(FormApp.EmailCollectionType.VERIFIED);
  } catch (e) {
    form.setCollectEmail(true);
  }
}

/** Sí/No como opción única, que es como lo dibuja la Torre. */
function _siNo(form, titulo, ayuda, obligatoria) {
  var item = form.addMultipleChoiceItem()
    .setTitle(titulo)
    .setChoiceValues(['Sí', 'No']);
  if (ayuda) item.setHelpText(ayuda);
  if (obligatoria) item.setRequired(true);
  return item;
}

/**
 * Escala 1–5 con los extremos rotulados.
 *
 * La Torre rotula los cinco puntos («1 · Nada» … «5 · Completamente»); Forms solo
 * deja rotular los extremos. El dominio numérico es el mismo, así que las
 * respuestas de los dos lados se pueden juntar sin traducir nada.
 */
function _escala(form, titulo, ayuda) {
  var item = form.addScaleItem()
    .setTitle(titulo)
    .setBounds(1, 5)
    .setLabels(ESCALA_MIN, ESCALA_MAX)
    .setRequired(true);
  if (ayuda) item.setHelpText(ayuda);
  return item;
}

/**
 * Crea la planilla de respuestas y la deja vinculada.
 *
 * Se hace acá y no a mano porque una respuesta que solo vive dentro del
 * formulario es incómoda de leer y de compartir, y en una fase de prueba lo que
 * se quiere es justamente mirar las respuestas abiertas juntas.
 */
function _vincularPlanilla(form) {
  var ss = SpreadsheetApp.create(TITULO + ' (respuestas)');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());
  return ss.getUrl();
}
