{
    'name': "Semantic Record Search",

    'description': "Uses AI to allow semantic search (sounds similar to...) of records in Odoo.",

    'author': "Jacob Peters",
    'website': "https://github.com/peters-J19/odoo-ai-modules",

    'category': 'Productivity/Semantic Record Search',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'application': True,

    # any module necessary for this one to work correctly
    'depends': ['base', 'ai', 'field_vector', 'helpdesk'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/semantic_search_wizard_views.xml',
        'views/semantic_search_ticket_views.xml',
        'views/semantic_search_ticket_embedding_views.xml',
        'views/semantic_search_menus.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'semantic_record_search/static/src/scss/semantic_search_navbar.scss',
        ],
    },
}

