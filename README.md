# All The Mods 9 - No Frills (Custom Fork)

> [!NOTE]
> This repository is a **custom community fork** of *All The Mods 9 - No Frills* maintained by [jusitnboggs](https://github.com/jusitnboggs). It is **not** the official upstream ATM team repository.

This fork enhances the base pack with additional mods (ProjectE, AutoEMC, Avaritia addons, AE2 expansions), custom ProjectE EMC conversion mappers, and custom pack tweaks.

## Setup & Cloning Instructions

To sync this customized pack directly into an existing Prism Launcher instance (even if the directory is non-empty):

1. Right-click your **ATM9 - No Frills** instance in Prism Launcher and select **Folder**.
2. Open the `minecraft` subfolder.
3. Open a command prompt or terminal inside that `minecraft` folder:
   - **Address Bar Method:** Click the folder path bar at the top of File Explorer, type `cmd` or `powershell`, and hit **Enter**.
4. Run the appropriate command below inside your terminal to clone/sync the repository into your folder:

   **For Windows Terminal / PowerShell (Default in Windows 11):**
   ```powershell
   git init; git remote add origin https://github.com/jusitnboggs/atm9nf.git; git fetch origin master; git reset --hard origin/master
   ```
   *(If `origin` already exists, use `git remote set-url origin https://github.com/jusitnboggs/atm9nf.git` instead of `add`).*

   **For Command Prompt (CMD):**
   ```cmd
   git init && git remote add origin https://github.com/jusitnboggs/atm9nf.git && git fetch origin master && git reset --hard origin/master
   ```

5. Double-click **`sync_pack.bat`** to automatically keep all custom pack configs, KubeJS scripts, and mod `.jar` files synced and updated.

---

## Safe Pack Update & Force-Sync Commands

To update or force-sync your pack files to the latest version on GitHub **without deleting your personal files or world saves**:

> [!TIP]
> **Safe Update (Preserves untracked user files & world saves)**
>
> **PowerShell:**
> ```powershell
> git fetch origin master; git reset --hard origin/master
> ```
>
> **Command Prompt (CMD):**
> ```cmd
> git fetch origin master && git reset --hard origin/master
> ```
>
> *Note: Avoid running `git clean -fd` unless you specifically want to delete all untracked local files.*

---

## Customized Features in this Fork

- **ProjectE & AutoEMC Integration**: Full EMC pricing support with custom `pe_custom_conversions` for:
  - Rechiseled & Rechiseled AE blocks
  - Chipped decorative variants
  - Croptopia food crafting fixes
  - Sophisticated Storage chest/barrel tier upgrades
  - Thermal Expansion & Thermal Extra press dies and materials
  - ComputerCraft turtles, Torchmaster Megatorch, and utility blocks
- **Added Mods & Expansions**: ProjectE, AutoEMC, ProjectCell, ProjectExpansion, Avaritia addons, Applied Energistics 2 expansions, and more.
- **Automated Mod Downloader**: Built-in script (`download_mods.bat`) to keep added and updated mods in sync.

---

Does "All The Mods" *really* contain ALL THE MODS? No, of course not.

Need Help?
======
When reporting an issue put the version number before the issue title! Such as [FULL][1.37] My game is broken! Also include any added mods you may have put in, into the description of the issue.

|You can also find us on Discord for help<br>or just to chat as well as Reddit|
|:------------:|
|<a href="https://discord.gg/3paFjuRfz9"><img src="https://discordapp.com/assets/fc0b01fe10a0b8c602fb0106d8189d9b.png" alt="Join us on Discord!"  width="200" height="68"></a>|
|<a href="https://www.reddit.com/r/allthemods"><img src="https://www.redditstatic.com/about/assets/reddit-logo.png" alt="/r/AllTheMods on Reddit"  width="200" height="67"></a>|
<br>

#### Modpacks:
+ [![All the Mods 0](http://cf.way2muchnoise.eu/372309.svg "ATM9") All The Mods 0 - ATM0](https://www.curseforge.com/minecraft/modpacks/all-the-mods-0)
+ [![All the Mods 1](http://cf.way2muchnoise.eu/242462.svg "ATM1") All The Mods 1 - ATM1](https://www.curseforge.com/minecraft/modpacks/all-the-mods)
+ [![All the Mods 2](http://cf.way2muchnoise.eu/253707.svg "ATM2") All The Mods 2 - ATM2](https://www.curseforge.com/minecraft/modpacks/all-the-mods-2)
+ [![All the Mods 3](http://cf.way2muchnoise.eu/269708.svg "ATM3") All The Mods 3 - ATM3](https://www.curseforge.com/minecraft/modpacks/all-the-mods-3)
+ [![All the Mods 3](http://cf.way2muchnoise.eu/301845.svg "ATM3R") All the Mods 3 - Remix - ATM3R](https://www.curseforge.com/minecraft/modpacks/all-the-mods-3-remix)
+ [![All the Mods 3 Expert](http://cf.way2muchnoise.eu/325396.svg "ATM3E") All The Mods 3 - Expert - ATM3E](https://www.curseforge.com/minecraft/modpacks/all-the-mods-3-expert)
+ [![All the Mods 4](http://cf.way2muchnoise.eu/316059.svg "ATM4") All The Mods 4 - ATM4](https://www.curseforge.com/minecraft/modpacks/all-the-mods-4)
+ [![All the Mods 5](http://cf.way2muchnoise.eu/357494.svg "ATM5") All The Mods 5 - ATM5](https://www.curseforge.com/minecraft/modpacks/all-the-mods-5)
+ [![All the Mods 6](http://cf.way2muchnoise.eu/381671.svg "ATM6") All The Mods 6 - ATM6](https://www.curseforge.com/minecraft/modpacks/all-the-mods-6)
+ [![All the Mods SLOP2](http://cf.way2muchnoise.eu/432480.svg "ATMSLOP2") All the Mods - Slice of Pi2](https://www.curseforge.com/minecraft/modpacks/all-the-mods-slice-of-pi2-atm-slop2)
+ [![All the Mods 6S](http://cf.way2muchnoise.eu/442246.svg "ATM6S") All the Mods 6 - To the Sky](https://www.curseforge.com/minecraft/modpacks/all-the-mods-6-to-the-sky-atm6s)
+ [![All the Magic Spellbound](http://cf.way2muchnoise.eu/500199.svg "ATMSpell") All the Magic Spellbound](https://www.curseforge.com/minecraft/modpacks/all-the-magic-spellbound)
+ [![All the Mods 7](http://cf.way2muchnoise.eu/426926.svg "ATM7") All The Mods 7 - ATM7](https://www.curseforge.com/minecraft/modpacks/all-the-mods-7)
+ [![All the Mods 7Sky](http://cf.way2muchnoise.eu/655739.svg "ATM7S") All the Mods 7 - To the Sky](https://www.curseforge.com/minecraft/modpacks/all-the-mods-7-to-the-sky)
+ [![All the Mods 8](http://cf.way2muchnoise.eu/520914.svg "ATM8") All The Mods 8 - ATM8](https://www.curseforge.com/minecraft/modpacks/all-the-mods-8)
+ [![All the Mods Gravitas](http://cf.way2muchnoise.eu/807446.svg "ATMG") All The Mods - Gravitas- ATMG](https://www.curseforge.com/minecraft/modpacks/all-the-mods-gravitas)
+ [![All the Mods 9](http://cf.way2muchnoise.eu/715572.svg "ATM9") All The Mods 9 - ATM9](https://www.curseforge.com/minecraft/modpacks/all-the-mods-9)
+ [![All the Mods 9 - No Frills](http://cf.way2muchnoise.eu/959010.svg "ATM9-NF") All The Mods 9 - ATM9 - No Frills](https://www.curseforge.com/minecraft/modpacks/all-the-mods-9-no-frills)
+ [![All the Mods Gravitas²](http://cf.way2muchnoise.eu/949996.svg "ATMG²") All The Mods Gravitas²- ATMG²](https://www.curseforge.com/minecraft/modpacks/all-the-mods-gravitas2)
+ [![Maul The Odds](http://cf.way2muchnoise.eu/987792.svg "MTO") Maul The Odds - MTO](https://www.curseforge.com/minecraft/modpacks/maul-the-odds)
+ [![All the Mods 9Sky](http://cf.way2muchnoise.eu/967745.svg "ATM9Sky") All The Mods 9 - To The Sky- ATM9Sky](https://www.curseforge.com/minecraft/modpacks/all-the-mods-9-to-the-sky)
+ [![All the Mods 10](http://cf.way2muchnoise.eu/925200.svg "ATM9Sky") All The Mods 10 - ATM10](https://www.curseforge.com/minecraft/modpacks/all-the-mods-10)
+ [![All the Magic Arcana](http://cf.way2muchnoise.eu/1190911.svg "ATMA") All The Magic - Arcana - ATMA](https://www.curseforge.com/minecraft/modpacks/all-the-magic-arcana)
