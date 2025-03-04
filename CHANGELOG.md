# CHANGELOG


## v0.2.0 (2025-03-04)

### Features

- **RPS-1230**: Propagate motion recordings
  ([#9](https://github.com/wandelbotsgmbh/wandelscript/pull/9),
  [`ab9879f`](https://github.com/wandelbotsgmbh/wandelscript/commit/ab9879fd485319ce4709df256cad009636d19496))

Co-authored-by: cbiering <christoph.biering@wandelbots.com>


## v0.1.0 (2025-02-26)

### Bug Fixes

- Check stdout on a run for a print message in a test
  ([`b4c6715`](https://github.com/wandelbotsgmbh/wandelscript/commit/b4c6715e7e4750a86e529b166fe05979d9a8d02f))

It's clear that the program's log contains "print something", since it contains `print("print
  something")`. However, upon looking closer, I realized that `runner.skill_run.logs` in fact does
  not contain the program's `print()` output, that's in 'runner.skill_run.stdout`.

Change the test accordingly.

- Fixed new nova execute interface & WS example
  ([#7](https://github.com/wandelbotsgmbh/wandelscript/pull/7),
  [`7fa497b`](https://github.com/wandelbotsgmbh/wandelscript/commit/7fa497bd92e77b7b0fd96625fae2ee383b0fa997))

---------

Co-authored-by: cbiering <christoph.biering@wandelbots.com>

- Remove unknown pytest options
  ([`1199ddf`](https://github.com/wandelbotsgmbh/wandelscript/commit/1199ddf607f0e164397ae423eee8e33f37b7f78e))

Extraenous ports over from the wandelbrain repo, can go away since their according packages are
  missing here.

- Typo
  ([`00312ce`](https://github.com/wandelbotsgmbh/wandelscript/commit/00312ce555d38d35f99764d34d77264db8761e98))

- **RPS-1006**: Fixed assoc does not work for tuple/array in Wandelscript
  ([#3](https://github.com/wandelbotsgmbh/wandelscript/pull/3),
  [`f264e17`](https://github.com/wandelbotsgmbh/wandelscript/commit/f264e17f1ba3bb9cd953c2b10fda84c334436a1e))

Co-authored-by: cbiering <christoph.biering@wandelbots.com>

### Chores

- Add `darglint` to pre-commit
  ([`dfbdf2f`](https://github.com/wandelbotsgmbh/wandelscript/commit/dfbdf2fd80962b609b542590b52834b0d2efedfe))

- Add dependency `numpy`
  ([`8658369`](https://github.com/wandelbotsgmbh/wandelscript/commit/8658369f08bbc9834a51584aece920b7316e2a5f))

- Add pre-commit
  ([`a405d87`](https://github.com/wandelbotsgmbh/wandelscript/commit/a405d87d3cda118d287afe2ba617ae084d086217))

Disable pre-commit trailing whitespace checks on `whitespaces.ws`. We have ws-file that concerns
  itself with whitespaces and trailing whitespaces. Consequently, don't lint trailing whitespaces on
  this file.

Add hooks for yamllint. Also add a copy of the `.yamllint` config from the `wandelbots-nova` project
  to align on our formatting standards.

Add check for sorting imports.

Add mypy to pre-commit.

- Add test showcasing async foreign function
  ([`111fcd2`](https://github.com/wandelbotsgmbh/wandelscript/commit/111fcd27bb0f514a00de8dd2cbc221af606d4a04))

- Added basic CI
  ([`fc07f94`](https://github.com/wandelbotsgmbh/wandelscript/commit/fc07f94373ca18ec659bfaf0855c806fc28c2cd9))

- Align import style of dataclasses with `from dataclass ...`
  ([`164a20f`](https://github.com/wandelbotsgmbh/wandelscript/commit/164a20fa508d2817eec410addc99792b07ad46cb))

Hereby align the import style to the style apparent in the rest of the project.

- Extend `.gitignore`
  ([`436d0c8`](https://github.com/wandelbotsgmbh/wandelscript/commit/436d0c8b992f7c0e60524db7fac892ecafa590fd))

Ignore - vim swap files - some reports - .vscode/ folders - .python-version file

Ignore reports for: - pytest - mypy

- Extend the Readme
  ([`72bf6b8`](https://github.com/wandelbotsgmbh/wandelscript/commit/72bf6b8c51d1d03a8594c1cfd51b3248cf2e0994))

Give it a more welcoming feel.

- Format some code
  ([`8790a07`](https://github.com/wandelbotsgmbh/wandelscript/commit/8790a07d60e113e81ed7e4fb8bf700fb3f7ee825))

- Groom `generate_parser.sh`
  ([`6f2013b`](https://github.com/wandelbotsgmbh/wandelscript/commit/6f2013b1e3ef3c566cfac73875e7a2daec49910e))

`$OUTPUT_DIR` seems unused. I hereby remove it entirely.

- Groom the examples a bit
  ([`9dc9ae0`](https://github.com/wandelbotsgmbh/wandelscript/commit/9dc9ae0e0d6c486a50c4d4382b3b6cb6e938c731))

Especially reformat the json files for readability and a somewhat more canonical formatting.

It may not be perfect but I consider it better than before.

- Introduce internal _types
  ([`1dbd9ba`](https://github.com/wandelbotsgmbh/wandelscript/commit/1dbd9bacfeb6dec5f589ad51b7f6c2c8700c020e))

- Mention async funcitons in ForeignFunction docstrings
  ([`2885bcc`](https://github.com/wandelbotsgmbh/wandelscript/commit/2885bcc3d89ab122f3418fad0113c4de4c14b06d))

- Migrated from wandelengine repository
  ([`93cf4c5`](https://github.com/wandelbotsgmbh/wandelscript/commit/93cf4c5cedf45544a5a3a43253f40a5a84c18313))

- Remove `geometricalgebra` cont'd
  ([`db5f1eb`](https://github.com/wandelbotsgmbh/wandelscript/commit/db5f1eb6711677c4d270e5bca7328cd33e43dd14))

- Remove `geometricalgebra` Episode III
  ([`766fe95`](https://github.com/wandelbotsgmbh/wandelscript/commit/766fe95f0820ca1b9dd5c982538b8964ea829708))

Revenge of the euclideans.

- Remove a wrong entry from the README
  ([`0c5a976`](https://github.com/wandelbotsgmbh/wandelscript/commit/0c5a976d1c7a1f1b08ec612dc020437febcc5bb2))

- Remove an unused import in a test file
  ([`3a573b6`](https://github.com/wandelbotsgmbh/wandelscript/commit/3a573b68dbcd506bca943e566c34f92df585a339))

- Remove dependency `geometricalgebra`
  ([`4b1500f`](https://github.com/wandelbotsgmbh/wandelscript/commit/4b1500f262526c6b8c6f1a0346446a2b9a5c9ee0))

- Remove Orientation and Position
  ([`c213534`](https://github.com/wandelbotsgmbh/wandelscript/commit/c21353416430c18bc8fa90d1fab5b1a1f880fb39))

Now largely consolidated in nova's Vector3d.

p

- Remove plugins_addons.{py,ws}
  ([`671f4b5`](https://github.com/wandelbotsgmbh/wandelscript/commit/671f4b5ed2e7928501184b63e4ece6d9d3cc5e97))

- Remove serializer stuff
  ([`9c1cd5e`](https://github.com/wandelbotsgmbh/wandelscript/commit/9c1cd5e0c6d7f0086a3fd96246c108b74359b7dc))

Serialization is part of the classes and types that the Nova SDK brings, so away with it here.

- Remove some builtins
  ([`3ea0e81`](https://github.com/wandelbotsgmbh/wandelscript/commit/3ea0e818eb17ff7ab93782400f942e865ff2147f))

Some of the builtinins rather belong into the Nova SDK.

First step is to identify to see what should go over. Then, remove it here and then add it to the
  Nova SDK. Then implement it here.

For now, identify and delete here in order to get a slim, working barebones Wandelscript.

- Remove some trailing whitespaces
  ([`31c5dd1`](https://github.com/wandelbotsgmbh/wandelscript/commit/31c5dd19632d9b532db79d29929174e961f04ff9))

Came via:

poetry run pre-commit run --all

This fixed a few other whitespace issues in files that were either autogenerated or where trailing
  spaces were intentional. I did not commit those changes.

- Remove stray `pytest.xml` reports
  ([`56b68d2`](https://github.com/wandelbotsgmbh/wandelscript/commit/56b68d2d636e084c691f789fd8b2bfebf9dd9a0b))

Ciao cacao

- Remove unused `Spline` class
  ([`90cc557`](https://github.com/wandelbotsgmbh/wandelscript/commit/90cc55772c2a676fc08c80036b371f9d3d818114))

- Remove unused `tcp_pose()` builtin function
  ([`90d20a4`](https://github.com/wandelbotsgmbh/wandelscript/commit/90d20a45fad1ddd79cb0814e7f78ba7548371f8e))

- Run poetry lock
  ([`88b9135`](https://github.com/wandelbotsgmbh/wandelscript/commit/88b91357af634e7eb542dd2d60aa38860927bca8))

- Slim some docstrings and improve few type hints
  ([`aeda758`](https://github.com/wandelbotsgmbh/wandelscript/commit/aeda758571aa40673f1fa727e5bc6f68e1595ba0))

- Transition dts / pyjectory
  ([`18aa673`](https://github.com/wandelbotsgmbh/wandelscript/commit/18aa6738e7cc6e300f470c9f22a69f15839aff76))

- Updated deps & using wandelbots-nova package
  ([`8123185`](https://github.com/wandelbotsgmbh/wandelscript/commit/81231857e8e8092bcb9e384d6ee48562b1f303d6))

- Upgrade dependency `wandelbots-nova`
  ([`9c15556`](https://github.com/wandelbotsgmbh/wandelscript/commit/9c155560ddfee820ee0ac87a391284e7bdd86acb))

Also update the README a bit.

- Use backport for ExceptionGroups
  ([`d082eaf`](https://github.com/wandelbotsgmbh/wandelscript/commit/d082eaf6df7b9918f8d7283a543e47a1716f5910))

ExceptionGroups have their 1st party introduction with Python 3.11.

### Features

- Add a foreign function interface
  ([`7495698`](https://github.com/wandelbotsgmbh/wandelscript/commit/7495698f5536ac54d5b61b5d7b82219d94d9b216))

Pronounced Fiffi.

Change an according test to also assert the usage of ForeignFunctions.

- Added LICENSE
  ([`8c559cf`](https://github.com/wandelbotsgmbh/wandelscript/commit/8c559cfa12492ab32fb4687ce40bd562218d8e5f))

- **RPS-1266**: Added release CI to wandelscript
  ([`be1a4ad`](https://github.com/wandelbotsgmbh/wandelscript/commit/be1a4ade1a0fceceba7f58d8ccd2baa48451d1c0))

- **RPS-1267**: Renamed skill to program
  ([`f6aaebc`](https://github.com/wandelbotsgmbh/wandelscript/commit/f6aaebc9c81bd5be89d99b61d7ff716e99c61e68))

- **RPS-898**: Wandelscript migration ([#5](https://github.com/wandelbotsgmbh/wandelscript/pull/5),
  [`57b1ff0`](https://github.com/wandelbotsgmbh/wandelscript/commit/57b1ff0a3e2b90096ce7d54be11188ca4e029472))

Co-authored-by: cbiering <christoph.biering@wandelbots.com>
