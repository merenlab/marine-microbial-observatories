# Marine Microbial Observatories

A repository to track time-series programs, large-scale expeditions, and coordination
networks that focus on generating molecular data on marine microbes.

**Website:** https://microbial-observatories.org

| | records |
|---|---|
| [Time-series programs](data/time-series) | 84 |
| [Large-scale expeditions](data/expeditions) | 13 |
| [Coordination networks](data/coordination-networks) | 33 |

## How this repository works

Each program is **one YAML file** in `data/`, named after its record id:

```
data/time-series/fram.yml
data/expeditions/tara.yml
data/coordination-networks/obon.yml
```

Those files are the *sole source of truth*, and everything else else is generated from them:

```
data/**.yml  ──▶  scripts/validate.py   checks every record against schema/
             └─▶  scripts/build.py      dist/data.json, dist/*.tsv, the website
```

Every field in time-series, expeditions, and coordination-networks are defined in their
respective schemas for validation:

- [`schema/time-series.schema.json`](schema/time-series.schema.json)
- [`schema/expeditions.schema.json`](schema/expeditions.schema.json)
- [`schema/coordination-networks.schema.json`](schema/coordination-networks.schema.json)

## Licence

Everything in this repository is licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) ([full text](LICENSE)). Use it
for anything, including commercially, provided you give credit:

> Marine Microbial Observatories, https://microbial-observatories.org, CC BY 4.0.

Two things are not ours to license:

- **The masthead photograph** is a NASA Earth Observatory image using Landsat 8 data from
  the U.S. Geological Survey. It is public domain, credited on the site and documented in
  [`site/assets/README.md`](site/assets/README.md).
- **The linked publications and archived datasets** carry whatever licences their
  publishers and archives apply. CC BY 4.0 covers this catalogue's own description of
  them, not their contents.

By contributing you agree that your contribution is licensed the same way.

## Contributing

Additions and corrections are welcome from anyone, whether or not you use GitHub. See
[CONTRIBUTING.md](CONTRIBUTING.md).

Contact details in this repository are published deliberately: the people listed want to
be reachable about their programs. Contact information are either entered by people
themselves, or by their close collaborators. If you are listed and would rather not be,
please send us an email and we will remove you immediately.

## Website

The content in this repository is served at https://microbial-observatories.org, but
you can test it locally by running the following:

```
python scripts/build.py && python3 -m http.server -d dist 8000
```

And then visiting the address on your browser: [http://localhost:8000](http://localhost:8000)

After cloning the repository, you will have to run this command once to install the dependencies:

```
pip install -r requirements.txt
```

---

`ABOUT.md` and `CONTRIBUTING.md` are the only copy of that text. `scripts/build.py` renders
them into `dist/pages/about.html` and `dist/pages/contribute.html`, and the site loads them
into its **About** and **Contribute** tabs.

If you are a developer or a maintainer of this resource, please remember: links written
for GitHub are rewritten for the web during the build. As in, `../../issues/...`
becomes an absolute GitHub URL, repo-relative paths become `blob/`/`tree/` links, links
between these two documents become in-site tab links, and bare email addresses become
`mailto:` links (except inside code blocks). So the same markdown reads correctly both on
GitHub and on the site.

You can run checks locally by running this command:

```sh
python3 scripts/validate.py
```

Which will show you all the issues with the YAML entries whether there are bona fide errors
that cause structural problems or warnings which should be addrssed but not essential for
everything to work. CI blocks on errors only, and fixing warnings is one of the best way
to help improve this resource.

## How it is put together

Each category is a single YAML file under `data/`, named after its permanent record id:

```
data/time-series/fram.yml
data/expeditions/tara.yml
data/coordination-networks/obon.yml
```

Those files are the only source of truth. This website, the downloadable TSV exports, and
`data.json` are all generated from them on every change. One file per record means a
correction to one program touches exactly one file, so contributions stay small and
reviewable and two people editing different programs never collide.

Every field is defined in a JSON Schema, and every pull request is validated against it
before it can be merged. That is what keeps the catalogue consistent as it grows, instead
of accumulating free text that no one can search or compare:

- [`schema/time-series.schema.json`](schema/time-series.schema.json)
- [`schema/expeditions.schema.json`](schema/expeditions.schema.json)
- [`schema/coordination-networks.schema.json`](schema/coordination-networks.schema.json)

The schemas double as the field documentation. Every property carries a description explaining
what belongs in it, and future updates should follow the same logic.
