"""Small, explicit and reviewable UI translations for VARYN consumer shell.

No online translation or automatic access to conversations. The English UI is
the default. User-selected language is stored as a non-secret local setting.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

LANGUAGES = {
    "English": "en",
    "Bahasa Indonesia": "id",
    "Español": "es",
    "Français": "fr",
}
LABELS = {value: key for key, value in LANGUAGES.items()}
DEFAULT_LANGUAGE = "en"

EN = {
    "home": "Home", "tasks": "Tasks", "apps": "Apps", "history": "History",
    "settings": "Settings", "workspace": "YOUR WORKSPACE", "personal": "Personal",
    "language": "Language", "expand": "Maximize", "restore": "Restore",
    "heading": "A little more room to think.", "subheading": "Ask a question, make a plan, or pick up where you left off.",
    "question": "What can I help you with today?", "send": "Send",
    "offline": "Try offline (demo)", "online_approval": "Allow one online request",
    "model_settings": "AI settings", "chat_title": "Conversation",
    "simulation": "Offline preview only. No AI model has responded.",
    "key_notice": "Online answers need your own API key and approval.",
    "shortcut_heading": "A good place to start",
    "task_short": "Plan something", "task_desc": "Keep track of what matters.",
    "apps_short": "Explore apps", "apps_desc": "See which integrations are planned.",
    "template_short": "Start with an example", "template_desc": "A useful starting point, ready to edit.",
    "template_prompt": "Help me make a plan for this week, starting with my three most important priorities.",
    "template_ready": "Example added. Review it before sending.",
    "tasks_intro": "Make space for the work that matters.",
    "task_name": "Task name", "due_date": "Due date (optional)",
    "date_example": "Example: 2026-11-09T14:30:00+07:00",
    "add": "Add task", "task_col": "TASK", "status_col": "STATUS",
    "due_col": "DUE DATE (UTC)", "complete": "Complete", "pause": "Pause",
    "cancel": "Cancel", "refresh": "Refresh", "next": "Next", "previous": "Previous",
    "apps_intro": "Your services, all in one place, when connected.",
    "apps_warning": "Nothing is connected yet. Each app requires its own authorization.",
    "type_col": "TYPE", "app_col": "APPLICATION / CAPABILITY",
    "connection_col": "CONNECTION", "not_connected": "Not connected",
    "apps_footnote": "This is a directory, not access to your accounts.",
    "history_title": "This session", "history_note": "Messages shown here stay in memory and disappear when the app closes.",
    "history_empty": "No messages in this session.",
    "prefs_intro": "Choose how VARYN looks and speaks to you.",
    "prefs_note": "Language changes take effect immediately. Your tasks and chat stay open.",
    "advanced": "Advanced tools", "close": "Close",
    "model_setup_hint": "Choose OpenRouter or DeepSeek to configure an online model.",
    "task_saved": "Task saved on this computer. Nothing was executed.",
    "task_invalid": "Check the task name and the due date, including its time zone.",
    "task_select": "Select a task first.", "task_changed": "Task status updated.",
    "task_change_invalid": "This task cannot be changed from its current state.",
    "task_count": "{total} saved tasks · {shown} shown. Tasks are not automatically executed.",
    "task_db_error": "Task database unavailable. No task was dispatched.",
    "due_error": "Could not refresh due dates. No task was executed.",
    "greeting": "Hi there. Write a message to get started.",
    "offline_reply": "DEMO ONLY: No AI model was called. Choose an online provider for a real answer.",
    "you": "You", "offline_name": "Offline preview",
    "settings_language": "Display language", "settings_ai": "Model configuration",
    "model_id": "Model ID", "input_price": "Input price (USD / 1M tokens)",
    "output_price": "Output price (USD / 1M tokens)", "review_prices": "I verified both prices and the model route.",
    "save_model": "Save model", "price_required": "Check the prices and confirm first.",
    "invalid_model": "Model or price invalid. Nothing was sent.",
    "model_saved": "Model configured. Each online message still needs approval.",
    "settings_explainer": "This is only required for online AI. The offline preview works without it.",
}
ID = {
    "home": "Beranda", "tasks": "Tugas", "apps": "Aplikasi", "history": "Riwayat",
    "settings": "Pengaturan", "workspace": "RUANG KERJAMU", "personal": "Pribadi",
    "language": "Bahasa", "expand": "Perbesar", "restore": "Pulihkan",
    "heading": "Lebih leluasa untuk berpikir.", "subheading": "Tanya sesuatu, susun rencana, atau lanjutkan pekerjaanmu.",
    "question": "Apa yang bisa kubantu hari ini?", "send": "Kirim",
    "offline": "Coba offline (demo)", "online_approval": "Izinkan satu permintaan online",
    "model_settings": "Pengaturan AI", "chat_title": "Percakapan",
    "simulation": "Hanya pratinjau offline. Belum ada jawaban dari AI.",
    "key_notice": "Jawaban online memerlukan API key sendiri dan persetujuanmu.",
    "shortcut_heading": "Mulai dari sini",
    "task_short": "Buat rencana", "task_desc": "Catat hal-hal yang penting.",
    "apps_short": "Jelajahi aplikasi", "apps_desc": "Lihat integrasi yang direncanakan.",
    "template_short": "Pakai contoh", "template_desc": "Contoh instruksi yang bisa kamu ubah.",
    "template_prompt": "Bantu saya membuat rencana minggu ini mulai dari tiga prioritas terpenting.",
    "template_ready": "Contoh dimasukkan. Periksa sebelum mengirim.",
    "tasks_intro": "Beri ruang untuk pekerjaan yang penting.",
    "task_name": "Nama tugas", "due_date": "Tanggal jatuh tempo (opsional)",
    "date_example": "Contoh: 2026-11-09T14:30:00+07:00",
    "add": "Tambah tugas", "task_col": "TUGAS", "status_col": "STATUS",
    "due_col": "JATUH TEMPO (UTC)", "complete": "Selesai", "pause": "Jeda",
    "cancel": "Batalkan", "refresh": "Segarkan", "next": "Berikutnya", "previous": "Sebelumnya",
    "apps_intro": "Semua layananmu dalam satu tempat setelah dihubungkan.",
    "apps_warning": "Belum ada yang terhubung. Setiap aplikasi perlu izin tersendiri.",
    "type_col": "JENIS", "app_col": "APLIKASI / KEMAMPUAN",
    "connection_col": "KONEKSI", "not_connected": "Belum terhubung",
    "apps_footnote": "Ini daftar integrasi, bukan akses ke akunmu.",
    "history_title": "Sesi ini", "history_note": "Pesan hanya ada selama aplikasi terbuka dan tidak tersimpan permanen.",
    "history_empty": "Belum ada pesan di sesi ini.",
    "prefs_intro": "Pilih cara VARYN tampil dan berbicara.",
    "prefs_note": "Bahasa berubah langsung. Tugas dan percakapan tetap terbuka.",
    "advanced": "Alat lanjutan", "close": "Tutup",
    "model_setup_hint": "Pilih OpenRouter atau DeepSeek untuk mengatur model online.",
    "task_saved": "Tugas disimpan di komputer ini. Tidak ada aksi yang dijalankan.",
    "task_invalid": "Periksa nama tugas dan tanggal, termasuk zona waktunya.",
    "task_select": "Pilih tugas terlebih dahulu.", "task_changed": "Status tugas diperbarui.",
    "task_change_invalid": "Status tugas ini tidak bisa diubah.",
    "task_count": "{total} tugas tersimpan · {shown} ditampilkan. Tugas tidak otomatis dijalankan.",
    "task_db_error": "Database tugas tidak tersedia. Tidak ada tugas dijalankan.",
    "due_error": "Gagal memperbarui jatuh tempo. Tidak ada tugas dijalankan.",
    "greeting": "Halo. Tulis pesan untuk memulai.",
    "offline_reply": "HANYA DEMO: Tidak ada model AI yang dipanggil. Pilih layanan online untuk jawaban sungguhan.",
    "you": "Kamu", "offline_name": "Pratinjau offline",
    "settings_language": "Bahasa tampilan", "settings_ai": "Konfigurasi model",
    "model_id": "ID model", "input_price": "Harga input (USD / 1 juta token)",
    "output_price": "Harga output (USD / 1 juta token)", "review_prices": "Saya sudah memeriksa kedua harga dan rute model.",
    "save_model": "Simpan model", "price_required": "Periksa dan konfirmasi harga dulu.",
    "invalid_model": "Model atau harga tidak valid. Tidak ada yang dikirim.",
    "model_saved": "Model disimpan. Setiap pesan online tetap perlu persetujuan.",
    "settings_explainer": "Hanya diperlukan untuk AI online. Pratinjau offline bisa tanpa ini.",
}
ES = {
    "home": "Inicio", "tasks": "Tareas", "apps": "Aplicaciones", "history": "Historial",
    "settings": "Ajustes", "workspace": "TU ESPACIO", "personal": "Personal",
    "language": "Idioma", "expand": "Maximizar", "restore": "Restaurar",
    "heading": "Un poco más de espacio para pensar.", "subheading": "Pregunta, organiza un plan o continúa tu trabajo.",
    "question": "¿En qué puedo ayudarte hoy?", "send": "Enviar",
    "offline": "Probar sin conexión (demo)", "online_approval": "Permitir una solicitud en línea",
    "model_settings": "Ajustes de IA", "chat_title": "Conversación",
    "simulation": "Solo vista previa sin conexión. Ninguna IA ha respondido.",
    "key_notice": "Las respuestas en línea requieren tu clave API y tu permiso.",
    "shortcut_heading": "Por dónde empezar",
    "task_short": "Crear un plan", "task_desc": "Organiza lo importante.",
    "apps_short": "Explorar aplicaciones", "apps_desc": "Consulta futuras integraciones.",
    "template_short": "Usar un ejemplo", "template_desc": "Un punto de partida editable.",
    "template_prompt": "Ayúdame a organizar esta semana empezando por mis tres prioridades.",
    "template_ready": "Ejemplo añadido. Revísalo antes de enviarlo.",
    "tasks_intro": "Haz espacio para lo que importa.",
    "task_name": "Nombre de tarea", "due_date": "Fecha límite (opcional)",
    "date_example": "Ejemplo: 2026-11-09T14:30:00+07:00",
    "add": "Añadir tarea", "task_col": "TAREA", "status_col": "ESTADO",
    "due_col": "FECHA (UTC)", "complete": "Completar", "pause": "Pausar",
    "cancel": "Cancelar", "refresh": "Actualizar", "next": "Siguiente", "previous": "Anterior",
    "apps_intro": "Tus servicios juntos, una vez conectados.",
    "apps_warning": "Todavía no hay conexiones. Cada servicio requiere autorización.",
    "type_col": "TIPO", "app_col": "APLICACIÓN / FUNCIÓN",
    "connection_col": "CONEXIÓN", "not_connected": "Sin conectar",
    "apps_footnote": "Este es un directorio, no acceso a tus cuentas.",
    "history_title": "Esta sesión", "history_note": "Los mensajes se borran al cerrar la aplicación.",
    "history_empty": "No hay mensajes en esta sesión.",
    "prefs_intro": "Elige cómo se ve y te habla VARYN.",
    "prefs_note": "El idioma cambia de inmediato. Tu trabajo permanece abierto.",
    "advanced": "Herramientas avanzadas", "close": "Cerrar",
    "model_setup_hint": "Selecciona OpenRouter o DeepSeek para configurar IA en línea.",
    "task_saved": "Tarea guardada en este ordenador. No se ejecutó ninguna acción.",
    "task_invalid": "Revisa el nombre y la fecha, incluida la zona horaria.",
    "task_select": "Selecciona una tarea.", "task_changed": "Estado actualizado.",
    "task_change_invalid": "No se puede cambiar el estado de esta tarea.",
    "task_count": "{total} tareas guardadas · {shown} visibles. No se ejecutan automáticamente.",
    "task_db_error": "Base de tareas no disponible. No se ejecutó ninguna tarea.",
    "due_error": "Error al revisar fechas. No se ejecutó ninguna tarea.",
    "greeting": "Hola. Escribe un mensaje para empezar.",
    "offline_reply": "SOLO DEMO: No se llamó a ningún modelo de IA. Elige un proveedor en línea.",
    "you": "Tú", "offline_name": "Vista previa offline",
    "settings_language": "Idioma de la interfaz", "settings_ai": "Configuración del modelo",
    "model_id": "ID de modelo", "input_price": "Precio de entrada (USD / 1M tokens)",
    "output_price": "Precio de salida (USD / 1M tokens)", "review_prices": "He verificado ambos precios y la ruta del modelo.",
    "save_model": "Guardar modelo", "price_required": "Comprueba y confirma ambos precios.",
    "invalid_model": "Modelo o precio no válido. No se envió nada.",
    "model_saved": "Modelo configurado. Cada mensaje necesita autorización.",
    "settings_explainer": "Solo se necesita para IA en línea. La demo funciona sin clave.",
}
FR = {
    "home": "Accueil", "tasks": "Tâches", "apps": "Applications", "history": "Historique",
    "settings": "Paramètres", "workspace": "VOTRE ESPACE", "personal": "Personnel",
    "language": "Langue", "expand": "Agrandir", "restore": "Restaurer",
    "heading": "Un peu plus d'espace pour réfléchir.", "subheading": "Posez une question, organisez un plan ou reprenez votre travail.",
    "question": "Comment puis-je vous aider aujourd'hui ?", "send": "Envoyer",
    "offline": "Essayer hors ligne (démo)", "online_approval": "Autoriser une requête en ligne",
    "model_settings": "Paramètres IA", "chat_title": "Conversation",
    "simulation": "Aperçu hors ligne uniquement. Aucune IA n'a répondu.",
    "key_notice": "Les réponses en ligne nécessitent votre clé API et votre accord.",
    "shortcut_heading": "Par où commencer",
    "task_short": "Préparer un plan", "task_desc": "Gardez l'essentiel en vue.",
    "apps_short": "Explorer les applications", "apps_desc": "Consultez les futures intégrations.",
    "template_short": "Utiliser un exemple", "template_desc": "Un point de départ modifiable.",
    "template_prompt": "Aide-moi à planifier ma semaine, en commençant par mes trois priorités.",
    "template_ready": "Exemple inséré. Vérifiez-le avant l'envoi.",
    "tasks_intro": "Faites de la place à ce qui compte.",
    "task_name": "Nom de la tâche", "due_date": "Échéance (facultatif)",
    "date_example": "Exemple : 2026-11-09T14:30:00+07:00",
    "add": "Ajouter une tâche", "task_col": "TÂCHE", "status_col": "STATUT",
    "due_col": "ÉCHÉANCE (UTC)", "complete": "Terminer", "pause": "Suspendre",
    "cancel": "Annuler", "refresh": "Actualiser", "next": "Suivant", "previous": "Précédent",
    "apps_intro": "Tous vos services au même endroit, une fois connectés.",
    "apps_warning": "Aucun service connecté. Une autorisation distincte est nécessaire.",
    "type_col": "TYPE", "app_col": "APPLICATION / FONCTION",
    "connection_col": "CONNEXION", "not_connected": "Non connecté",
    "apps_footnote": "Ceci est un annuaire, sans accès à vos comptes.",
    "history_title": "Cette session", "history_note": "Les messages disparaissent à la fermeture de l'application.",
    "history_empty": "Aucun message dans cette session.",
    "prefs_intro": "Personnalisez la langue et l'apparence de VARYN.",
    "prefs_note": "La langue change immédiatement. Vos tâches restent ouvertes.",
    "advanced": "Outils avancés", "close": "Fermer",
    "model_setup_hint": "Choisissez OpenRouter ou DeepSeek pour configurer l'IA en ligne.",
    "task_saved": "Tâche enregistrée localement. Aucune action exécutée.",
    "task_invalid": "Vérifiez le titre, la date et le fuseau horaire.",
    "task_select": "Sélectionnez une tâche.", "task_changed": "Statut mis à jour.",
    "task_change_invalid": "Impossible de modifier ce statut.",
    "task_count": "{total} tâches · {shown} affichées. Pas d'exécution automatique.",
    "task_db_error": "Base des tâches inaccessible. Aucune action exécutée.",
    "due_error": "Échec de la mise à jour. Aucune tâche exécutée.",
    "greeting": "Bonjour. Écrivez un message pour commencer.",
    "offline_reply": "DÉMO UNIQUEMENT : aucun modèle d'IA n'a été appelé.",
    "you": "Vous", "offline_name": "Aperçu hors ligne",
    "settings_language": "Langue de l'interface", "settings_ai": "Configuration du modèle",
    "model_id": "Identifiant du modèle", "input_price": "Prix entrée (USD / 1M jetons)",
    "output_price": "Prix sortie (USD / 1M jetons)", "review_prices": "J'ai vérifié les deux prix et le modèle.",
    "save_model": "Enregistrer le modèle", "price_required": "Vérifiez et confirmez les deux prix.",
    "invalid_model": "Modèle ou prix invalide. Rien n'a été envoyé.",
    "model_saved": "Modèle enregistré. Chaque requête exige une autorisation.",
    "settings_explainer": "Uniquement pour l'IA en ligne. La démo fonctionne sans clé.",
}
TRANSLATIONS = {"en": EN, "id": ID, "es": ES, "fr": FR}

def text(language, key, **arguments):
    table = TRANSLATIONS.get(language, EN)
    output = table.get(key, EN[key])
    return output.format(**arguments) if arguments else output

def config_path():
    base = os.environ.get("LOCALAPPDATA")
    directory = Path(base) if base else Path.home() / "AppData" / "Local"
    return directory / "VARYN" / "preferences.json"

def load_language():
    path = config_path()
    try:
        if not path.is_file() or path.stat().st_size > 1024:
            return DEFAULT_LANGUAGE
        raw = json.loads(path.read_text(encoding="utf-8"))
        value = raw.get("language") if type(raw) is dict else None
        return value if value in TRANSLATIONS else DEFAULT_LANGUAGE
    except (ValueError, UnicodeError, OSError):
        return DEFAULT_LANGUAGE

def save_language(language):
    if language not in TRANSLATIONS:
        raise ValueError("Unsupported display language")
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Only a harmless language code is persisted. No API key or chat history.
    temporary = path.with_suffix(".tmp")
    try:
        temporary.write_text(json.dumps({"language": language}), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
