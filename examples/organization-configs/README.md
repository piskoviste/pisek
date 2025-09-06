# Organization config examples 

Here you can find examples of organization configs that provide defaults
for all of the organization's tasks. It is useful to put some options there
your organization always uses (like `judge_type`) or enable checks disabled
by default.

Organization configs are stored in the `configs` subdirectory of the `pisek`
settings folder. The folder is automatically detected at the topmost level
of the git repository root. You can override the location of the `pisek`
settings folder with either `--pisek-dir` or `$PISEK_DIRECTORY`.

```
my-organization
├── .git
└── pisek
    └── configs
        ├── cms-base-v1
        ├── cms-batch-v1
        └── cms-communication-v1
```

It might be a good idea to add versions to your organization configs, as if you want to make
a breaking change, you can simply start using a new version.

## CMS

For CMS we provide three configs: `cms-base-v1`, `cms-batch-v1` and `cms-communication-v1`.
Note that both batch and communication inherit from `cms-base-v1`, therefore you must copy
it to the `pisek/configs` folder too.

## Opendata

For opendata tasks we provide the `opendata-v1` organization config.
